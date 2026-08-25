/** @type {import('next').NextConfig} */
const fs = require("fs");
const os = require("os");
const path = require("path");

function lanHosts() {
  const hosts = ["127.0.0.1", "localhost"];
  for (const list of Object.values(os.networkInterfaces())) {
    for (const net of list || []) {
      if (net.internal) continue;
      if (net.family !== "IPv4" && net.family !== 4) continue;
      hosts.push(net.address);
    }
  }
  return hosts;
}

function tunnelHosts() {
  const hosts = ["*.trycloudflare.com"];
  const file = path.resolve(__dirname, "..", "..", "data", "tunnel-url.txt");
  try {
    const raw = fs.readFileSync(file, "utf8").trim();
    const hostname = new URL(raw).hostname;
    if (hostname.endsWith(".trycloudflare.com") && hostname !== "api.trycloudflare.com") {
      hosts.push(hostname);
    }
  } catch {
    /* tunnel file optional */
  }
  return hosts;
}

const nextConfig = {
  reactStrictMode: false,
  devIndicators: false,
  allowedDevOrigins: [...lanHosts(), ...tunnelHosts()],
  transpilePackages: [
    "three",
    "@react-three/fiber",
    "@react-three/drei",
    "@react-three/postprocessing",
    "vis-network",
    "vis-data",
  ],
  async rewrites() {
    const api = process.env.HAKIM_API_ORIGIN ?? "http://127.0.0.1:8000";
    return [{ source: "/api-hakim/:path*", destination: `${api}/:path*` }];
  },
};

module.exports = nextConfig;
