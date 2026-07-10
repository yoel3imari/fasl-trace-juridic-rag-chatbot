import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Standalone output enables minimal production Docker images
  output: "standalone",
};

export default nextConfig;
