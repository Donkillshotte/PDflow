import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Studio reads markdown and spawns course scripts from the parent repo.
  serverExternalPackages: [],
  // Hide Next.js DevTools "N Issues" badge — students confuse it with ORFS errors.
  // Real ORFS health is shown in FlowLabTerminal digest (0 ERROR · N WARNING).
  devIndicators: false,
};

export default nextConfig;
