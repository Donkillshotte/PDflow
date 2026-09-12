import type { NextConfig } from "next";

const scriptSrc = ["'self'", "'unsafe-inline'"];
if (process.env.NODE_ENV !== "production") {
  // Next's development client/evaluator needs this; production does not.
  scriptSrc.push("'unsafe-eval'");
}

const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=()",
  },
  {
    key: "Content-Security-Policy",
    value: [
      "default-src 'self'",
      `script-src ${scriptSrc.join(" ")}`,
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: blob:",
      "font-src 'self' data:",
      "connect-src 'self'",
      // Monaco creates its language workers from local blob URLs. Keep the
      // runtime self-hosted while allowing those workers to start under the
      // desktop CSP.
      "worker-src 'self' blob:",
      "frame-ancestors 'none'",
      "base-uri 'self'",
      "form-action 'self'",
    ].join("; "),
  },
];

const nextConfig: NextConfig = {
  // The desktop builder packages the standalone Next server beside the
  // Tauri shell. Browser development keeps the normal Next layout.
  output: process.env.PD_FLOW_DESKTOP_BUILD === "1" ? "standalone" : undefined,
  // Studio reads markdown and spawns course scripts from the parent repo.
  serverExternalPackages: [],
  // Hide Next.js DevTools "N Issues" badge — students confuse it with ORFS errors.
  // Real ORFS health is shown in FlowLabTerminal digest (0 ERROR · N WARNING).
  devIndicators: false,
  // Keep Next's worker pool within the four-CPU heavy-job budget. This is
  // deliberately explicit because the host may expose many more CPUs than
  // the PDflow cgroup is allowed to consume.
  experimental: {
    cpus: 4,
    memoryBasedWorkersCount: false,
    staticGenerationMaxConcurrency: 4,
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: securityHeaders,
      },
    ];
  },
};

export default nextConfig;
