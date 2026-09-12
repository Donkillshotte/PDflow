import { LabWorkspace } from "@/components/LabWorkspace";

export const metadata = {
  title: "Lab bench · OpenROAD Studio",
  description: "Physics ledger and experiment comparison on real finishes.",
};

export default function LabPage() {
  return (
    <main className="lab-page">
      <LabWorkspace />
    </main>
  );
}
