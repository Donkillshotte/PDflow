import { LabBench } from "@/components/LabBench";
import { DsePanel } from "@/components/flowlab/DsePanel";

export const metadata = {
  title: "Lab bench · OpenROAD Studio",
  description: "Physics ledger and experiment comparison on real finishes.",
};

export default function LabPage() {
  return (
    <main className="lab-page">
      <LabBench />
      <div id="dse" className="lab-dse-wrap">
        <DsePanel />
      </div>
    </main>
  );
}
