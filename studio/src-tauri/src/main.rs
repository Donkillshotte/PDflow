#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::Serialize;
use std::ffi::OsString;
use std::fmt::Write as FmtWrite;
use std::fs::OpenOptions;
use std::io::{Read as IoRead, Write as IoWrite};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};
use tauri::{Manager, State};

#[cfg(unix)]
use std::os::unix::process::CommandExt;

const AGENT_PORT: u16 = 43219;
const FRONTEND_PORT: u16 = 43217;
const DESKTOP_LOG_MAX_BYTES: usize = 16 * 1024 * 1024;
const DESKTOP_LOG_MARKER: &[u8] =
    b"\n[PDflow desktop log cap reached; see the rotated .1 log for the previous session]\n";

struct AgentProcess(Mutex<Option<Child>>);
struct FrontendProcess(Mutex<Option<Child>>);

#[derive(Serialize)]
struct AgentStatus {
    running: bool,
    pid: Option<u32>,
    port: u16,
}

fn validate_repo_root(raw: &str) -> Result<PathBuf, String> {
    let root = Path::new(raw)
        .canonicalize()
        .map_err(|error| format!("invalid repository root: {error}"))?;
    if !root.join("learn").is_dir() || !root.join("config/pdflow/tool_registry.json").is_file() {
        return Err("repository root is not a PDflow checkout".to_string());
    }
    Ok(root)
}

fn discover_repo_root() -> Result<PathBuf, String> {
    if let Ok(raw) = std::env::var("PD_FLOW_REPO_ROOT") {
        if !raw.trim().is_empty() {
            return validate_repo_root(&raw);
        }
    }
    let current = std::env::current_dir()
        .map_err(|error| format!("unable to inspect desktop working directory: {error}"))?;
    for candidate in current.ancestors() {
        if candidate.join("learn").is_dir()
            && candidate.join("config/pdflow/tool_registry.json").is_file()
        {
            return Ok(candidate.to_path_buf());
        }
    }
    Err("unable to discover a PDflow checkout from the desktop working directory".to_string())
}

fn agent_token() -> String {
    if let Ok(value) = std::env::var("PD_FLOW_AGENT_TOKEN") {
        if !value.trim().is_empty() {
            return value;
        }
    }
    let bytes = (|| {
        let mut bytes = [0_u8; 32];
        let mut source = std::fs::File::open("/dev/urandom").ok()?;
        source.read_exact(&mut bytes).ok()?;
        Some(bytes.to_vec())
    })()
    .unwrap_or_else(|| {
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|duration| duration.as_nanos())
            .unwrap_or_default();
        now.to_le_bytes().to_vec()
    });
    let mut token = String::new();
    for byte in bytes.iter().take(32) {
        let _ = write!(&mut token, "{byte:02x}");
    }
    token
}

fn prepend_path(existing: Option<OsString>, entries: &[PathBuf]) -> OsString {
    let mut values = entries.to_vec();
    if let Some(value) = existing {
        values.extend(std::env::split_paths(&value));
    }
    std::env::join_paths(values).unwrap_or_default()
}

fn log_path(root: &Path, name: &str) -> PathBuf {
    root.join(".pdflow").join("agent").join(name)
}

fn rotate_log(path: &Path) -> Result<(), String> {
    if !path.is_file() {
        return Ok(());
    }
    let rotated = path.with_file_name(format!(
        "{}.1",
        path.file_name()
            .and_then(|value| value.to_str())
            .unwrap_or("pdflow.log")
    ));
    if rotated.exists() {
        std::fs::remove_file(&rotated)
            .map_err(|error| format!("unable to rotate {}: {error}", path.display()))?;
    }
    std::fs::rename(path, &rotated)
        .map_err(|error| format!("unable to rotate {}: {error}", path.display()))
}

struct BoundedLogWriter {
    file: std::fs::File,
    bytes_written: usize,
    truncated: bool,
}

impl BoundedLogWriter {
    fn append(&mut self, data: &[u8]) {
        if data.is_empty() || self.truncated {
            return;
        }
        let payload_limit = DESKTOP_LOG_MAX_BYTES.saturating_sub(DESKTOP_LOG_MARKER.len());
        let remaining = payload_limit.saturating_sub(self.bytes_written);
        let allowed = remaining.min(data.len());
        if allowed > 0 && self.file.write_all(&data[..allowed]).is_ok() {
            self.bytes_written += allowed;
        }
        if allowed < data.len() {
            let marker = &DESKTOP_LOG_MARKER[..DESKTOP_LOG_MARKER
                .len()
                .min(DESKTOP_LOG_MAX_BYTES.saturating_sub(self.bytes_written))];
            let _ = self.file.write_all(marker);
            self.bytes_written += marker.len();
            self.truncated = true;
        }
    }

    fn flush(&mut self) {
        let _ = self.file.flush();
    }
}

fn prepare_stream_log(root: &Path, name: &str) -> Result<Arc<Mutex<BoundedLogWriter>>, String> {
    let log_dir = root.join(".pdflow").join("agent");
    std::fs::create_dir_all(&log_dir)
        .map_err(|error| format!("unable to create desktop log directory: {error}"))?;
    let path = log_path(root, name);
    rotate_log(&path)?;
    let file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(&path)
        .map_err(|error| format!("unable to open {}: {error}", path.display()))?;
    Ok(Arc::new(Mutex::new(BoundedLogWriter {
        file,
        bytes_written: 0,
        truncated: false,
    })))
}

fn append_bounded_bootstrap_log(root: &Path, message: &str) {
    let log_dir = root.join(".pdflow").join("agent");
    if std::fs::create_dir_all(&log_dir).is_err() {
        return;
    }
    let path = log_path(root, "desktop-bootstrap.log");
    let line = format!("{message}\n").into_bytes();
    let current = path
        .metadata()
        .map(|metadata| metadata.len() as usize)
        .unwrap_or(0);
    if current >= DESKTOP_LOG_MAX_BYTES {
        let _ = rotate_log(&path);
    }
    let Ok(mut file) = OpenOptions::new().create(true).append(true).open(&path) else {
        return;
    };
    let current = file
        .metadata()
        .map(|metadata| metadata.len() as usize)
        .unwrap_or(0);
    let payload_limit = DESKTOP_LOG_MAX_BYTES.saturating_sub(DESKTOP_LOG_MARKER.len());
    let allowed = payload_limit.saturating_sub(current).min(line.len());
    if allowed > 0 {
        let _ = file.write_all(&line[..allowed]);
    }
    if allowed < line.len() {
        let marker = &DESKTOP_LOG_MARKER[..DESKTOP_LOG_MARKER
            .len()
            .min(DESKTOP_LOG_MAX_BYTES.saturating_sub(current.saturating_add(allowed)))];
        let _ = file.write_all(marker);
    }
    let _ = file.flush();
}

fn attach_log_pump<R>(reader: R, writer: Arc<Mutex<BoundedLogWriter>>)
where
    R: IoRead + Send + 'static,
{
    thread::spawn(move || {
        let mut reader = reader;
        let mut buffer = [0_u8; 64 * 1024];
        loop {
            match reader.read(&mut buffer) {
                Ok(0) => break,
                Ok(size) => {
                    if let Ok(mut guard) = writer.lock() {
                        guard.append(&buffer[..size]);
                    } else {
                        break;
                    }
                }
                Err(_) => break,
            }
        }
        if let Ok(mut guard) = writer.lock() {
            guard.flush();
        }
    });
}

fn attach_process_logs(child: &mut Child, writer: Arc<Mutex<BoundedLogWriter>>) {
    if let Some(stdout) = child.stdout.take() {
        attach_log_pump(stdout, Arc::clone(&writer));
    }
    if let Some(stderr) = child.stderr.take() {
        attach_log_pump(stderr, writer);
    }
}

fn append_bootstrap_log(root: &Path, message: &str) {
    append_bounded_bootstrap_log(root, message);
}

#[cfg(unix)]
fn isolate_process_group(command: &mut Command) {
    // The closure runs in the child after fork and before exec. It only calls
    // the async-signal-safe setpgid(2) primitive, so the desktop owns a
    // process group for every long-lived child it starts. The parent-death
    // signal closes the crash/kill path where Tauri cannot emit RunEvent::Exit.
    let desktop_pid = unsafe { libc::getpid() };
    unsafe {
        command.pre_exec(move || {
            if libc::setpgid(0, 0) != 0 {
                return Err(std::io::Error::last_os_error());
            }
            #[cfg(target_os = "linux")]
            if libc::prctl(libc::PR_SET_PDEATHSIG, libc::SIGKILL as libc::c_ulong) != 0 {
                return Err(std::io::Error::last_os_error());
            }
            // A parent can exit between fork and prctl(2). Refuse to exec in
            // that case instead of creating an unowned long-lived service.
            if libc::getppid() != desktop_pid {
                return Err(std::io::Error::new(
                    std::io::ErrorKind::Interrupted,
                    "PDflow desktop exited before child initialization",
                ));
            }
            Ok(())
        });
    }
}

#[cfg(not(unix))]
fn isolate_process_group(_command: &mut Command) {}

fn agent_python() -> OsString {
    if let Some(value) = std::env::var_os("PD_FLOW_AGENT_PYTHON") {
        if !value.is_empty() {
            return value;
        }
    }
    for candidate in ["/usr/bin/python3", "/usr/local/bin/python3"] {
        let path = Path::new(candidate);
        if path.is_file() {
            return path.as_os_str().to_owned();
        }
    }
    OsString::from("python3")
}

fn configure_native_environment(command: &mut Command, root: &Path) {
    let prefix = std::env::var_os("PD_FLOW_EDA_PREFIX")
        .map(PathBuf::from)
        .or_else(|| {
            std::env::var_os("HOME")
                .map(PathBuf::from)
                .map(|home| home.join(".local/pdflow-eda"))
        });
    let mut path_entries = vec![
        root.join("tools/native/bin"),
        root.join("learn/tools/xyce/bin"),
        root.join("learn/tools/fastercap"),
        root.join("learn/tools/hotspot"),
    ];
    let mut library_entries = Vec::new();
    if let Some(prefix) = prefix.as_ref() {
        path_entries.push(prefix.join("usr/bin"));
        library_entries.push(prefix.join("usr/lib/x86_64-linux-gnu"));
        library_entries.push(prefix.join("usr/lib"));
        command.env("PD_FLOW_EDA_PREFIX", prefix);
    }
    let mut python_path_entries = vec![root.join("learn")];
    let system_python_packages = PathBuf::from("/usr/lib/python3/dist-packages");
    if system_python_packages.is_dir() {
        python_path_entries.push(system_python_packages);
    }
    let python_path = std::env::join_paths(python_path_entries)
        .unwrap_or_else(|_| root.join("learn").into_os_string());
    command
        .env(
            "PATH",
            prepend_path(std::env::var_os("PATH"), &path_entries),
        )
        .env(
            "LD_LIBRARY_PATH",
            prepend_path(std::env::var_os("LD_LIBRARY_PATH"), &library_entries),
        )
        .env("PYTHONPATH", python_path)
        .env_remove("PYTHONHOME")
        .env_remove("PYTHONSTARTUP")
        .env("PYTHONNOUSERSITE", "1")
        .env("PYTHONUNBUFFERED", "1");
}

fn terminate_child(child: &mut Child) {
    #[cfg(unix)]
    {
        // Check the direct child before signalling a negative PGID. This
        // avoids sending a signal to a reused PID when a child already exited.
        match child.try_wait() {
            Ok(Some(_)) | Err(_) => return,
            Ok(None) => {}
        }
        let pid = child.id() as libc::pid_t;
        unsafe {
            let _ = libc::kill(-pid, libc::SIGTERM);
        }
        let deadline = Instant::now() + Duration::from_secs(3);
        loop {
            match child.try_wait() {
                Ok(Some(_)) => return,
                Ok(None) if Instant::now() < deadline => {
                    thread::sleep(Duration::from_millis(100));
                }
                Ok(None) | Err(_) => break,
            }
        }
        unsafe {
            let _ = libc::kill(-pid, libc::SIGKILL);
        }
        let _ = child.wait();
        return;
    }

    #[cfg(not(unix))]
    {
        let _ = child.kill();
        let _ = child.wait();
    }
}

fn stop_process(process: &Mutex<Option<Child>>) {
    if let Ok(mut guard) = process.lock() {
        if let Some(mut child) = guard.take() {
            terminate_child(&mut child);
        }
    }
}

fn start_frontend_server(
    app: &tauri::AppHandle,
    state: &FrontendProcess,
    root: &Path,
) -> Result<(), String> {
    let resource_dir = app
        .path()
        .resource_dir()
        .map_err(|error| format!("unable to resolve desktop resources: {error}"))?;
    let next_root = resource_dir.join("next-standalone");
    let node = resource_dir.join("node-runtime").join("node");
    let server = next_root.join("server.js");
    if !node.is_file() {
        return Err(format!(
            "bundled Node runtime is missing: {}",
            node.display()
        ));
    }
    if !server.is_file() {
        return Err(format!(
            "bundled Next server is missing: {}",
            server.display()
        ));
    }
    let log_writer = prepare_stream_log(root, "next-server.log")?;
    let mut command = Command::new(&node);
    command
        .arg(&server)
        .current_dir(&next_root)
        .env("HOSTNAME", "127.0.0.1")
        .env("PORT", FRONTEND_PORT.to_string())
        .env("PD_FLOW_REPO_ROOT", root)
        .env(
            "PD_FLOW_AGENT_URL",
            format!("http://127.0.0.1:{AGENT_PORT}"),
        )
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    configure_native_environment(&mut command, root);
    isolate_process_group(&mut command);
    let mut child = command
        .spawn()
        .map_err(|error| format!("unable to start bundled Next server: {error}"))?;
    attach_process_logs(&mut child, log_writer);
    let mut guard = state
        .0
        .lock()
        .map_err(|_| "frontend process lock poisoned".to_string())?;
    *guard = Some(child);
    Ok(())
}

fn launch_local_agent(state: &AgentProcess, root: &Path, port: u16) -> Result<AgentStatus, String> {
    let mut guard = state.0.lock().map_err(|_| "agent lock poisoned")?;
    append_bootstrap_log(
        root,
        &format!(
            "launch requested root={} port={} python={}",
            root.display(),
            port,
            Path::new(&agent_python()).display()
        ),
    );
    if let Some(child) = guard.as_mut() {
        match child.try_wait() {
            Ok(None) => {
                return Ok(AgentStatus {
                    running: true,
                    pid: Some(child.id()),
                    port,
                });
            }
            Ok(Some(_)) | Err(_) => *guard = None,
        }
    }
    let token = agent_token();
    let python = agent_python();
    append_bootstrap_log(
        root,
        &format!(
            "agent command prepared python={}",
            Path::new(&python).display()
        ),
    );
    let mut command = Command::new(&python);
    command
        .arg("-m")
        .arg("pdflow_agent")
        .arg("--repo-root")
        .arg(&root)
        .arg("--port")
        .arg(port.to_string())
        .current_dir(&root)
        .env("PD_FLOW_REPO_ROOT", &root)
        .env("PD_FLOW_AGENT_PORT", port.to_string())
        .env("PD_FLOW_AGENT_TOKEN", &token)
        .stdin(Stdio::null());
    append_bootstrap_log(root, "agent stdio setup starting");
    let log_writer = match prepare_stream_log(&root, "agent.log") {
        Ok(writer) => writer,
        Err(error) => {
            append_bootstrap_log(root, &format!("agent stdio setup failed: {error}"));
            return Err(error);
        }
    };
    append_bootstrap_log(root, "agent stdio setup complete");
    command.stdout(Stdio::piped()).stderr(Stdio::piped());
    configure_native_environment(&mut command, &root);
    isolate_process_group(&mut command);
    append_bootstrap_log(
        root,
        &format!(
            "spawning python={} cwd={} path={} pythonpath={}",
            Path::new(&python).display(),
            root.display(),
            command
                .get_envs()
                .find(|(key, _)| *key == "PATH")
                .and_then(|(_, value)| value)
                .and_then(|value| value.to_str())
                .unwrap_or("<non-utf8>"),
            command
                .get_envs()
                .find(|(key, _)| *key == "PYTHONPATH")
                .and_then(|(_, value)| value)
                .and_then(|value| value.to_str())
                .unwrap_or("<non-utf8>"),
        ),
    );
    let mut child = command.spawn().map_err(|error| {
        let message = format!(
            "unable to start PDflow local agent: {error} (python={}, root={})",
            Path::new(&python).display(),
            root.display()
        );
        append_bootstrap_log(root, &message);
        message
    })?;
    attach_process_logs(&mut child, log_writer);
    let pid = child.id();
    append_bootstrap_log(root, &format!("agent spawned pid={pid}"));
    *guard = Some(child);
    Ok(AgentStatus {
        running: true,
        pid: Some(pid),
        port,
    })
}

#[tauri::command]
fn start_local_agent(
    state: State<'_, AgentProcess>,
    repo_root: Option<String>,
    port: u16,
) -> Result<AgentStatus, String> {
    let root = match repo_root {
        Some(raw) => validate_repo_root(&raw)?,
        None => discover_repo_root()?,
    };
    launch_local_agent(&state, &root, port)
}

#[tauri::command]
fn stop_local_agent(state: State<'_, AgentProcess>) -> Result<AgentStatus, String> {
    stop_process(&state.0);
    Ok(AgentStatus {
        running: false,
        pid: None,
        port: AGENT_PORT,
    })
}

#[tauri::command]
fn local_agent_status(state: State<'_, AgentProcess>, port: u16) -> Result<AgentStatus, String> {
    let mut guard = state.0.lock().map_err(|_| "agent lock poisoned")?;
    if let Some(child) = guard.as_mut() {
        if child
            .try_wait()
            .map_err(|error| error.to_string())?
            .is_none()
        {
            return Ok(AgentStatus {
                running: true,
                pid: Some(child.id()),
                port,
            });
        }
        *guard = None;
    }
    Ok(AgentStatus {
        running: false,
        pid: None,
        port,
    })
}

fn main() {
    let app = tauri::Builder::default()
        .manage(AgentProcess(Mutex::new(None)))
        .manage(FrontendProcess(Mutex::new(None)))
        .setup(|app| {
            if !cfg!(debug_assertions) {
                let root = discover_repo_root().map_err(|error| {
                    Box::new(std::io::Error::new(std::io::ErrorKind::Other, error))
                        as Box<dyn std::error::Error>
                })?;
                start_frontend_server(&app.handle(), &app.state::<FrontendProcess>(), &root)
                    .map_err(|error| {
                        Box::new(std::io::Error::new(std::io::ErrorKind::Other, error))
                            as Box<dyn std::error::Error>
                    })?;
                launch_local_agent(&app.state::<AgentProcess>(), &root, AGENT_PORT).map_err(
                    |error| {
                        Box::new(std::io::Error::new(std::io::ErrorKind::Other, error))
                            as Box<dyn std::error::Error>
                    },
                )?;
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            start_local_agent,
            stop_local_agent,
            local_agent_status
        ])
        .build(tauri::generate_context!())
        .expect("error while building PDflow desktop");
    app.run(|app_handle, event| {
        if matches!(event, tauri::RunEvent::Exit) {
            stop_process(&app_handle.state::<AgentProcess>().0);
            stop_process(&app_handle.state::<FrontendProcess>().0);
        }
    });
}
