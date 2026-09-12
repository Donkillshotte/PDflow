import fs from "fs";
import path from "path";
import Link from "next/link";
import {
  type PkgPreview,
  type SystemPreview,
  type ThermalPreview,
} from "@/components/PkgHubPanel";
import { PackageWorkspace } from "@/components/PackageWorkspace";
import { LEARN_ROOT } from "@/lib/course";
import { isCurrentReport } from "@/lib/liveReports";

export const metadata = {
  title: "PKG · System PDN · OpenROAD Studio",
  description: "System PDN ladder and Phase 2. Product signoff stays on finish.",
};

function readReport<T>(name: string): T | null {
  const abs = path.join(LEARN_ROOT, "sim/reports", name);
  if (!isCurrentReport(abs)) return null;
  try {
    return JSON.parse(fs.readFileSync(abs, "utf8")) as T;
  } catch {
    return null;
  }
}

export default async function PkgPage({
  searchParams,
}: {
  searchParams?: Promise<{ platform?: string; variant?: string }>;
}) {
  const params = await searchParams;
  const platform = params?.platform;
  const system = readReport<SystemPreview>("system_pdn_flowlab.json");
  const thermal = readReport<ThermalPreview>("thermal_signoff_flowlab.json");
  const pkg = readReport<PkgPreview>("pkg_signoff_flowlab.json");

  return (
    <main className="pkg-page">
      <header className="page-head">
        <p className="eyebrow">Package</p>
        <h1>PKG · System PDN and Phase 2</h1>
        <p>
          Board / package ladder, HotSpot, dummy RDL and the native ASAP7 Lab
          system path. Chip IR, STA, DRC, and LVS close on{" "}
          <Link href="/flow?phase=finish#signoff">finish</Link> via{" "}
          <code>signoff_all</code>.
        </p>
      </header>
      <PackageWorkspace
        system={system}
        thermal={thermal}
        pkg={pkg}
        asap7={platform !== "course"}
        initialVariant={params?.variant}
      />
    </main>
  );
}
