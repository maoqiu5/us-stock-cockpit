import type { NextConfig } from "next";

const basePath = process.env.NEXT_PUBLIC_BASE_PATH || "";

const nextConfig: NextConfig = {
  output: "standalone",
  basePath,
  experimental: {
    devtoolSegmentExplorer: false,
  },
  env: {
    NEXT_PUBLIC_API_BASE: process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000",
    NEXT_PUBLIC_BASE_PATH: basePath
  }
};

export default nextConfig;
