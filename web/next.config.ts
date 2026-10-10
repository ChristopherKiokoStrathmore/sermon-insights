import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Static files only. The pipeline cannot run on the host that serves this site.
  output: "export",
  images: { unoptimized: true },
};

export default nextConfig;
