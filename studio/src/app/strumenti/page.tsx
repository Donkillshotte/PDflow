import { Suspense } from "react";
import StrumentiClient from "./strumenti-client";

export default function StrumentiPage() {
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
      <StrumentiClient />
    </Suspense>
  );
}
