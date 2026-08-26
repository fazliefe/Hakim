/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: false,
  // Sol alt köşedeki Next.js dev-mode rozeti demo sırasında sahnede görünmesin.
  // Üretim build'inde (next build && next start) zaten çıkmaz; dev'de de kapalı olsun.
  devIndicators: false,
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
