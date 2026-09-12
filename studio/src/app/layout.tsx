import { Suspense } from "react";
import type { Metadata } from "next";
import { ToastProvider } from "@/components/ToastProvider";
import { AppShell } from "@/components/AppShell";
import "./globals.css";
import "./workbench.css";

export const metadata: Metadata = {
  title: "OpenROAD · Physical Design Studio",
  description:
    "FlowLab course and signoff actions on OpenROAD / ORFS (Nangate45).",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <ToastProvider>
          <Suspense fallback={<div className="app-shell-loading" aria-busy="true">Loading PDflow workspace…</div>}>
            <AppShell>{children}</AppShell>
          </Suspense>
        </ToastProvider>
      </body>
    </html>
  );
}
