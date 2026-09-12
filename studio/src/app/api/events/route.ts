import { agentResponse } from "@/lib/agentClient";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  const incoming = new URL(req.url);
  const requestedSince = incoming.searchParams.get("since");
  const since = requestedSince?.trim() || "latest";
  const remote = await agentResponse(
    "/v1/events?since=" + encodeURIComponent(since),
  );
  if (remote?.ok && remote.body) {
    return new Response(remote.body, {
      status: 200,
      headers: {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Content-Type": "text/event-stream; charset=utf-8",
        "X-Accel-Buffering": "no",
      },
    });
  }
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    start(controller) {
      const payload = JSON.stringify({
        event_id: 0,
        type: "agent.offline",
        timestamp: Date.now() / 1000,
        payload: { fallback: true },
      });
      controller.enqueue(
        encoder.encode("event: status\ndata: " + payload + "\n\n"),
      );
      controller.close();
    },
  });
  return new Response(stream, {
    status: 200,
    headers: {
      "Cache-Control": "no-cache",
      "Content-Type": "text/event-stream; charset=utf-8",
    },
  });
}
