import { isAllowedAction, streamCourseAction } from "@/lib/run";

export const dynamic = "force-dynamic";
export const maxDuration = 900;

export async function GET(req: Request) {
  const url = new URL(req.url);
  const action = url.searchParams.get("action") ?? "";
  if (!isAllowedAction(action)) {
    return new Response(`Azione non consentita: ${action}`, { status: 400 });
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
