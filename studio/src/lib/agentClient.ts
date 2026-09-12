import fs from "fs";
import path from "path";
import { REPO_ROOT } from "./course";

const DEFAULT_AGENT_URL = "http://127.0.0.1:43219";

function agentUrl(): string {
  return (process.env.PD_FLOW_AGENT_URL || DEFAULT_AGENT_URL).replace(/\/+$/, "");
}

function agentToken(): string | undefined {
  if (process.env.PD_FLOW_AGENT_TOKEN) return process.env.PD_FLOW_AGENT_TOKEN;
  try {
    return (
      fs
        .readFileSync(
          path.join(REPO_ROOT, ".pdflow", "agent", "agent.token"),
          "utf8",
        )
        .trim() || undefined
    );
  } catch {
    return undefined;
  }
}

function requestHeaders(init: RequestInit = {}): Headers {
  const token = agentToken();
  const headers = new Headers(init.headers);
  if (token) headers.set("X-PDFlow-Token", token);
  return headers;
}

export async function agentResponse(
  endpoint: string,
  init: RequestInit = {},
): Promise<Response | null> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 30000);
  try {
    return await fetch(agentUrl() + endpoint, {
      ...init,
      headers: requestHeaders(init),
      signal: controller.signal,
      cache: "no-store",
    });
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

export async function agentFetch<T>(
  endpoint: string,
  init: RequestInit = {},
): Promise<T | null> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 2500);
  try {
    const response = await fetch(agentUrl() + endpoint, {
      ...init,
      headers: requestHeaders(init),
      signal: controller.signal,
      cache: "no-store",
    });
    if (!response.ok) return null;
    return (await response.json()) as T;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

export function agentBaseUrl(): string {
  return agentUrl();
}
