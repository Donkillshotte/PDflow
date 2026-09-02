import { Suspense } from "react";
import ToolsClient from "./tools-client";

export default function ToolsPage() {
  return (
    <Suspense
      fallback={
        <main>
          <header className="page-head">
            <h1>Tools</h1>
            <p>Loading…</p>
          </header>
        </main>
      }
    >
      <ToolsClient />
    </Suspense>
  );
}
