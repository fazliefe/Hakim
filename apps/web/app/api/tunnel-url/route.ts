import { access, readFile } from "fs/promises";
import os from "os";
import path from "path";
import QRCode from "qrcode";
import { NextResponse } from "next/server";

async function tunnelFile() {
  const candidates = [
    path.resolve(process.cwd(), "..", "..", "data", "tunnel-url.txt"),
    path.resolve(process.cwd(), "data", "tunnel-url.txt"),
  ];
  for (const file of candidates) {
    try {
      await access(file);
      return file;
    } catch {
      /* try next */
    }
  }
  return candidates[0];
}

function normalizeTunnel(raw: string): string | null {
  try {
    const parsed = new URL(raw.trim());
    if (parsed.protocol !== "https:") return null;
    if (parsed.hostname === "api.trycloudflare.com") return null;
    if (!parsed.hostname.endsWith(".trycloudflare.com")) return null;
    return parsed.origin;
  } catch {
    return null;
  }
}

function lanOrigins(): string[] {
  const found: string[] = [];
  for (const list of Object.values(os.networkInterfaces())) {
    for (const net of list ?? []) {
      if (net.internal) continue;
      if (String(net.family) !== "IPv4" && String(net.family) !== "4") continue;
      found.push(`http://${net.address}:3000`);
    }
  }
  return found.sort((a, b) => lanScore(a) - lanScore(b));
}

function lanScore(origin: string): number {
  if (origin.includes("192.168.")) return 0;
  if (origin.includes("//10.")) return 1;
  return 2;
}

export async function GET() {
  let tunnel: string | null = null;
  try {
    const raw = await readFile(await tunnelFile(), "utf8");
    tunnel = normalizeTunnel(raw);
  } catch {
    tunnel = null;
  }
  const lan = lanOrigins();
  const origin = tunnel ?? lan[0] ?? null;
  const target = origin ? `${origin.replace(/\/+$/, "")}/giris` : null;
  let qr: string | null = null;
  if (target) {
    qr = await QRCode.toDataURL(target, {
      width: 360,
      margin: 2,
      errorCorrectionLevel: "M",
      color: { dark: "#1a1206", light: "#ffffff" },
    });
  }
  return NextResponse.json({
    url: origin,
    target,
    qr,
    tunnel,
    lan,
    via: tunnel ? "tunnel" : lan[0] ? "lan" : null,
  });
}
