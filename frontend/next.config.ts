import os from "node:os";
import type { NextConfig } from "next";

function lanDevOrigins(): string[] {
  const origins = new Set<string>(["localhost", "127.0.0.1", "[::1]"]);
  for (const addrs of Object.values(os.networkInterfaces())) {
    for (const addr of addrs ?? []) {
      if (!addr.internal && addr.address.includes(".")) {
        origins.add(addr.address);
      }
    }
  }
  return [...origins];
}

const nextConfig: NextConfig = {
  // Standalone is for Docker/Compose. On Vercel (Next 16.3+), it breaks
  // onBuildComplete: ENOENT .next/next-server.js.nft.json.
  output: process.env.VERCEL ? undefined : "standalone",
  allowedDevOrigins: lanDevOrigins(),
};

export default nextConfig;
