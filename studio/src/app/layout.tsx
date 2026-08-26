import type { Metadata } from "next";
import { Syne, Figtree, IBM_Plex_Mono } from "next/font/google";
import { SiteNav } from "@/components/SiteNav";
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
    "Interfaccia grafica per il corso hands-on di physical design con OpenROAD e ORFS.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="it">
      <body className={`${display.variable} ${body.variable} ${mono.variable}`}>
        <div className="shell">
          <SiteNav />
          {children}
        </div>
      </body>
    </html>
  );
}
