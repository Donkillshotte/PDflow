"use client";

type TauriInternals = {
  invoke<T>(command: string, args?: Record<string, unknown>): Promise<T>;
};

declare global {
  interface Window {
    __TAURI_INTERNALS__?: TauriInternals;
  }
}

export function isDesktopShell(): boolean {
  return typeof window !== "undefined" && Boolean(window.__TAURI_INTERNALS__);
}

export async function startDesktopAgent(): Promise<boolean> {
  if (!isDesktopShell()) return false;
  try {
    await window.__TAURI_INTERNALS__?.invoke("start_local_agent", {
      repoRoot: null,
      port: 43219,
    });
    return true;
  } catch {
    return false;
  }
}
