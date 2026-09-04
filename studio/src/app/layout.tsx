import type { Metadata } from "next";
import { Syne, Figtree, IBM_Plex_Mono } from "next/font/google";
import { SiteNav } from "@/components/SiteNav";
import { ToastProvider } from "@/components/ToastProvider";
import { CommandPalette } from "@/components/CommandPalette";
import "./globals.css";

const display = Syne({
  subsets: ["latin"],
  variable: "--font-display",
  weight: ["600", "700", "800"],
});

const body = Figtree({
  subsets: ["latin"],
  variable: "--font-body",
  weight: ["400", "500", "600", "700"],
});

const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  weight: ["400", "500"],
});

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
      <body className={`${display.variable} ${body.variable} ${mono.variable}`}>
        <ToastProvider>
          <div className="shell">
            <SiteNav />
            <div id="main">{children}</div>
          </div>
          <CommandPalette />
        </ToastProvider>
      </body>
    </html>
  );
}
