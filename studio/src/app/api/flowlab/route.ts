import { NextResponse } from "next/server";
import {
  getFlowlabStatus,
  readParams,
  readRtl,
  resetRtl,
  writeParams,
  writeRtl,
  type FlowlabParams,
} from "@/lib/flowlab";
import { authorizeStudioMutation, rejectOversizedBody } from "@/lib/runAuth";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const status = getFlowlabStatus();
    return NextResponse.json({
      ...status,
      rtl: readRtl(),
      params: readParams(),
    });
  } catch (e) {
    return NextResponse.json(
      { error: e instanceof Error ? e.message : String(e) },
      { status: 500 },
    );
  }
}

export async function PUT(req: Request) {
  const denied = authorizeStudioMutation(req, "FlowLab write");
  if (denied) {
    return denied;
  }
  const tooLarge = rejectOversizedBody(req, 1024 * 1024);
  if (tooLarge) {
    return tooLarge;
  }
  try {
    const body = (await req.json()) as {
      rtl?: string;
      params?: Partial<FlowlabParams>;
      resetRtl?: boolean;
    };
    let rtl: string | undefined;
    let params = readParams();

    if (body.resetRtl) {
      rtl = resetRtl();
    } else if (typeof body.rtl === "string") {
      writeRtl(body.rtl);
      rtl = readRtl();
    }

    if (body.params) {
      params = writeParams(body.params);
    }

    return NextResponse.json({
      ok: true,
      ...getFlowlabStatus(),
      rtl: rtl ?? readRtl(),
      params,
      message: body.resetRtl
        ? "RTL restored from upstream GCD"
        : "FlowLab saved",
    });
  } catch (e) {
    return NextResponse.json(
      { error: e instanceof Error ? e.message : String(e), ok: false },
      { status: 400 },
    );
  }
}
