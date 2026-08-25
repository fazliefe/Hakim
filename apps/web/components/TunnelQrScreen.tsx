"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";

type Payload = {
  url: string | null;
  target: string | null;
  qr: string | null;
  tunnel: string | null;
  lan: string[];
  via: "tunnel" | "lan" | null;
};

export function TunnelQrScreen() {
  const router = useRouter();
  const [payload, setPayload] = useState<Payload | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const load = () => {
      fetch("/api/tunnel-url", { cache: "no-store" })
        .then((res) => res.json() as Promise<Payload>)
        .then((body) => {
          if (!cancelled) setPayload(body);
        })
        .catch(() => {
          if (!cancelled) setPayload(null);
        });
    };
    load();
    const timer = window.setInterval(load, 2500);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  const target = payload?.target;
  const viaLan = payload?.via === "lan";

  async function copy() {
    if (!target) return;
    try {
      await navigator.clipboard.writeText(target);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  }

  return (
    <main className="qr-screen">
      <header className="qr-brand">
        <Image src="/hakim-emblem.png" alt="" width={36} height={36} />
        <strong>HÂKİM</strong>
      </header>
      <section className="qr-card">
        <p className="qr-kicker">Mobil erişim</p>
        <h1>QR kodu okutun</h1>
        <p className="qr-lede">
          {viaLan
            ? "Telefonu bilgisayarla aynı Wi-Fi ağına alın. Cloudflare tüneli bu ağda kapalı."
            : "Telefon kamerası bu kodu açınca giriş sayfasına gider."}
        </p>
        {target && payload?.qr ? (
          <>
            <img className="qr-image" src={payload.qr} alt="HÂKİM QR kodu" width={360} height={360} />
            <p className="qr-url">{target}</p>
            <div className="qr-actions">
              <button type="button" className="btn-gold" onClick={() => void copy()}>
                {copied ? "Kopyalandı" : "Adresi Kopyala"}
              </button>
              <button type="button" className="btn-ghost" onClick={() => router.back()}>
                Geri
              </button>
              <Link className="btn-ghost" href="/giris">
                Giriş
              </Link>
            </div>
          </>
        ) : (
          <p className="qr-wait">Adres alınamadı. apps/web içinde npm run dev çalışıyor olmalı.</p>
        )}
      </section>
    </main>
  );
}
