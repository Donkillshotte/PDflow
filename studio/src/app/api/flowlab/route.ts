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
        ? "RTL ripristinato dal golden GCD"
        : "FlowLab salvato",
    });
  } catch (e) {
    return NextResponse.json(
      { error: e instanceof Error ? e.message : String(e), ok: false },
      { status: 400 },
    );
  }
}
