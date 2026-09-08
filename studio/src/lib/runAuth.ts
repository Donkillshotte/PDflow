/**
 * Guard Studio mutations and heavy process launches.
 *
 * Browser requests from the Studio itself are allowed when their Origin or
 * Referer matches the request host. Non-browser automation must provide the
 * optional bearer token. This keeps the UI usable when STUDIO_RUN_TOKEN is
 * configured while refusing cross-site requests and unauthenticated clients.
 */
export function authorizeStudioMutation(
  req: Request,
  label = "mutation",
): Response | null {
  const token = process.env.STUDIO_RUN_TOKEN?.trim();
  const auth = req.headers.get("authorization") ?? "";
  if (token && auth === `Bearer ${token}`) {
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
      error: token
        ? `${label} requires same-origin Origin/Referer or STUDIO_RUN_TOKEN bearer`
        : `${label} requires same-origin Origin/Referer`,
      code: "forbidden",
    },
    { status: 403 },
  );
}

/** Reject oversized declared request bodies before a route calls req.json(). */
export function rejectOversizedBody(
  req: Request,
  maxBytes: number,
): Response | null {
  const raw = req.headers.get("content-length");
  if (raw === null) {
    return null;
  }
  const length = Number(raw);
  if (!Number.isSafeInteger(length) || length < 0) {
    return Response.json(
      { error: "invalid content-length", code: "payload_too_large" },
      { status: 413 },
    );
  }
  if (length > maxBytes) {
    return Response.json(
      {
        error: `request body exceeds ${maxBytes} bytes`,
        code: "payload_too_large",
      },
      { status: 413 },
    );
  }
  return null;
}

/** Backwards-compatible name for the heavy run stream route. */
export function authorizeRunRequest(req: Request): Response | null {
  return authorizeStudioMutation(req, "run stream");
}
