import fs from "fs";
import path from "path";
import { ChildProcess, spawn } from "child_process";
import { LEARN_ROOT } from "./course";
import { resultsDir, STAGE_GUI_TARGETS, detectDisplay } from "./open";

const LOCK = () => path.join(LEARN_ROOT, ".studio-web.lock");
const DEFAULT_PORT = Number(process.env.STUDIO_OR_WEB_PORT || 43190);

type WebLock = {
  pid: number;
  port: number;
  artifact: string;
  stage: string;
  url: string;
  startedAt: string;
};

function readLock(): WebLock | null {
  try {
    if (!fs.existsSync(LOCK())) return null;
    return JSON.parse(fs.readFileSync(LOCK(), "utf8")) as WebLock;
  } catch {
    return null;
  }
}

function writeLock(lock: WebLock) {
  fs.mkdirSync(path.dirname(LOCK()), { recursive: true });
  fs.writeFileSync(LOCK(), JSON.stringify(lock, null, 2) + "\n");
}

function clearLock() {
  try {
    fs.unlinkSync(LOCK());
  } catch {
    /* ignore */
  }
}

function pidAlive(pid: number) {
  try {
    process.kill(pid, 0);
    return true;
  } catch (e) {
    return Boolean(e && typeof e === "object" && "code" in e && e.code === "EPERM");
  }
}

function primaryArtifactForStage(stage: string): string | null {
  const items = STAGE_GUI_TARGETS[stage];
  if (!items?.length) return null;
  const odb = items.find((i) => i.artifact.endsWith(".odb") && i.kind === "openroad");
  return (odb ?? items[0]).artifact;
}

export function viewerStatus() {
  const lock = readLock();
  if (!lock) return { running: false as const, display: detectDisplay() };
  if (!pidAlive(lock.pid)) {
    clearLock();
    return { running: false as const, display: detectDisplay() };
  }
  return { running: true as const, ...lock, display: detectDisplay() };
}

export function stopViewer(): { ok: boolean; message: string } {
  const lock = readLock();
  if (!lock) return { ok: true, message: "nessun viewer attivo" };
  try {
    process.kill(lock.pid, "SIGTERM");
    setTimeout(() => {
      try {
        process.kill(lock.pid, "SIGKILL");
      } catch {
        /* ignore */
      }
    }, 1500);
  } catch {
    /* ignore */
  }
  clearLock();
  return { ok: true, message: `viewer fermato (pid ${lock.pid})` };
}

export function startViewer(
  stage: string,
  variant = "learn",
): {
  ok: boolean;
  message: string;
  url?: string;
  port?: number;
  artifact?: string;
} {
  const artifact = primaryArtifactForStage(stage);
  if (!artifact) {
    return { ok: false, message: `stage sconosciuto: ${stage}` };
  }
  const abs = path.join(
    /*turbopackIgnore: true*/ resultsDir(variant),
    artifact,
  );
  if (!fs.existsSync(abs)) {
    return {
      ok: false,
      message: `Artefatto mancante: ${artifact} — esegui prima la fase ${stage} (${variant})`,
    };
  }

  const existing = viewerStatus();
  if (existing.running) {
    if (existing.artifact === artifact && existing.stage === stage) {
      return {
        ok: true,
        message: "viewer già attivo su questo artefatto",
        url: existing.url,
        port: existing.port,
        artifact,
      };
    }
    stopViewer();
  }

  const port = DEFAULT_PORT;
  const child: ChildProcess = spawn(
    "openroad",
    [
      "-no_init",
      "-no_splash",
      "-web",
      "-web_port",
      String(port),
      "-db",
      abs,
    ],
    {
      detached: true,
      stdio: "ignore",
      env: { ...process.env, DISPLAY: process.env.DISPLAY || ":1" },
    },
  );
  child.unref();
  if (!child.pid) {
    return { ok: false, message: "spawn openroad -web fallito" };
  }

  const url = `http://127.0.0.1:${port}/`;
  writeLock({
    pid: child.pid,
    port,
    artifact,
    stage,
    url,
    startedAt: new Date().toISOString(),
  });

  return {
    ok: true,
    message: `OpenROAD Web Viewer su ${artifact} (${variant})`,
    url,
    port,
    artifact,
  };
}
