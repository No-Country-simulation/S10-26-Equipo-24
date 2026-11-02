
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  experimental: {
    agentFeedback: true,
  },

  cacheComponents: true,
  partialPrefetching: true,

  // Define explícitamente la raíz del proyecto.
  turbopack: {
    root: process.cwd(),

    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },

  // Permite solicitudes de desarrollo desde la IP local.
  allowedDevOrigins: ["192.168.56.1"],
};

export default nextConfig;
