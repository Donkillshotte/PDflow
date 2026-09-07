/** Guard heavy /api/run/stream triggers (CSRF / bearer). */
export function authorizeRunRequest(req: Request): Response | null {
  const token = process.env.STUDIO_RUN_TOKEN?.trim();
  if (token) {
    const auth = req.headers.get("authorization") ?? "";
    if (auth !== `Bearer ${token}`) {
      return Response.json(
        { error: "unauthorized", code: "forbidden" },
        { status: 403 },
      );
    }
    return null;
  }

  const origin = req.headers.get("origin");
  const host = req.headers.get("host");
  if (origin && host) {
    try {
      const o = new URL(origin);
      if (o.host !== host) {
        return Response.json(
          { error: "cross-origin refused", code: "forbidden" },
          { status: 403 },
        );
      }
    } catch {
      return Response.json(
        { error: "bad origin", code: "forbidden" },
        { status: 403 },
      );
    }
    return null;
  }

  const referer = req.headers.get("referer");
  if (referer && host) {
    try {
      const r = new URL(referer);
      if (r.host !== host) {
        return Response.json(
          { error: "cross-site referer refused", code: "forbidden" },
          { status: 403 },
        );
      }
    } catch {
      return Response.json(
        { error: "bad referer", code: "forbidden" },
        { status: 403 },
      );
    }
    return null;
  }

  return Response.json(
    {
      error:
        "run stream requires same-origin Origin/Referer or STUDIO_RUN_TOKEN bearer",
      code: "forbidden",
    },
    { status: 403 },
  );
}
