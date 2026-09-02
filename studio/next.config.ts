import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Studio reads markdown and spawns course scripts from the parent repo.
  serverExternalPackages: [],
  // Hide Next.js DevTools "N Issues" badge — students confuse it with ORFS errors.
  // Real ORFS health is shown in FlowLabTerminal digest (0 ERROR · N WARNING).
  devIndicators: false,
  async redirects() {
    return [
      { source: "/flusso", destination: "/flow", permanent: true },
      { source: "/flusso/:path*", destination: "/flow/:path*", permanent: true },
      { source: "/strumenti", destination: "/tools", permanent: true },
      { source: "/strumenti/:path*", destination: "/tools/:path*", permanent: true },
      { source: "/materiali", destination: "/materials", permanent: true },
      { source: "/materiali/:path*", destination: "/materials/:path*", permanent: true },
      { source: "/lezioni", destination: "/lessons", permanent: true },
      { source: "/lezioni/:path*", destination: "/lessons/:path*", permanent: true },
    ];
  },
};

export default nextConfig;
