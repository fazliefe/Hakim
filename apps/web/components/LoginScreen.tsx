"use client";

import Image from "next/image";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { InteractiveScale } from "@/components/InteractiveScale";
import { SystemStatus, getSystemStatus } from "@/lib/api";

const CHECK_LABELS: Record<string, string> = {
  api: "API",
  elasticsearch: "Arama",
  neo4j: "Graf",
  postgres: "Arşiv",
  yazim: "Yazım",
};

export function LoginScreen() {
  const router = useRouter();
  const [email, setEmail] = useState("hukukcu@hakim.local");
  const [password, setPassword] = useState("");
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const biasRef = useRef(0);
  const onBiasChange = useCallback((v: number) => {
    biasRef.current = v;
  }, []);

  useEffect(() => {
    getSystemStatus()
      .then(setStatus)
      .catch(() =>
        setStatus({
          status: "kapalı",
          service: "hakim-api",
          ready: false,
              checks: { api: "kapalı", elasticsearch: "kapalı", neo4j: "kapalı", postgres: "kapalı", yazim: "kapalı" },
        })
      );
  }, []);

  function enter(kind: "uye" | "misafir") {
    window.sessionStorage.setItem("hakim-auth", kind);
    window.sessionStorage.setItem("hakim-scale-bias", String(biasRef.current));
    router.push("/arastirma");
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    enter("uye");
  }

  return (
    <main className="login-screen cinematic">
      <div className="login-stage">
        <InteractiveScale onBiasChange={onBiasChange} size="hero" />
      </div>

      <header className="login-titlecard">
        <p className="login-kicker">Kaynak odaklı hukuk zekâsı</p>
        <h1 className="login-hero-title">HÂKİM</h1>
        <p className="login-hero-copy">Kodun dili, geleceğin Hakimi.</p>
      </header>

      <section className="login-panel" aria-label="HÂKİM giriş">
        <div className="login-card">
          <Image
            src="/hakim-emblem.png"
            alt="HÂKİM amblemi"
            width={72}
            height={72}
            className="login-emblem"
            priority
          />
          <h2>Adalet salonuna giriş</h2>
          <p className="login-slogan">Mevzuat, içtihat ve atıf grafı tek salonda.</p>

          <div className="system-pills" aria-label="Sistem durumu">
            {Object.entries(CHECK_LABELS).map(([key, label]) => {
              const ok = status?.checks[key as keyof SystemStatus["checks"]] === "ok";
              return (
                <span key={key} className={`sys-pill ${ok ? "ok" : "down"}`}>
                  <i />
                  {label}
                </span>
              );
            })}
          </div>

          <form className="login-form" onSubmit={onSubmit}>
            <label>
              E-posta
              <input
                type="email"
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </label>
            <label>
              Parola
              <input
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Demo için boş bırakılabilir"
              />
            </label>
            <div className="login-actions">
              <button className="btn-gold" type="submit">
                Salona gir
              </button>
              <button className="btn-ghost" type="button" onClick={() => enter("misafir")}>
                Misafir oturumu
              </button>
            </div>
          </form>
        </div>
      </section>
    </main>
  );
}
