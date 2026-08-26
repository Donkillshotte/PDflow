import { isAllowedAction, streamCourseAction } from "@/lib/run";
import { preflightAction } from "@/lib/jobs";

export const dynamic = "force-dynamic";
export const maxDuration = 900;

export async function GET(req: Request) {
  const url = new URL(req.url);
  const action = url.searchParams.get("action") ?? "";
  if (!isAllowedAction(action)) {
    return Response.json(
      { error: `Azione non consentita: ${action}`, code: "forbidden" },
      { status: 400 },
    );
  }

  const pf = preflightAction(action);
  if (!pf.ok) {
    return Response.json(
      {
        error: pf.message,
        code: pf.code,
        lock: "lock" in pf ? pf.lock : undefined,
        dep: "dep" in pf ? pf.dep : undefined,
        missing: "missing" in pf ? pf.missing : undefined,
      },
      { status: pf.code === "locked" ? 409 : 412 },
    );
  }

  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    async start(controller) {
      const send = (obj: unknown) => {
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(obj)}\n\n`));
      };
      try {
        for await (const ev of streamCourseAction(action, {
          signal: req.signal,
          skipPreflight: true,
        })) {
          send(ev);
        }
      } catch (e) {
        send({
          type: "error",
          message: e instanceof Error ? e.message : String(e),
        });
      } finally {
        controller.close();
      }
    },
    cancel() {
      /* AbortSignal on req handles process kill via streamCourseAction */
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
    },
  });
}
