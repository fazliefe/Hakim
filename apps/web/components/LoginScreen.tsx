"use client";

import Image from "next/image";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { InteractiveScale } from "@/components/InteractiveScale";
import { PasswordInput } from "@/components/PasswordInput";
import {
  loginAccount,
  registerAccount,
  requestPasswordReset,
  resendVerification,
  resetPassword,
  verifyAccount,
} from "@/lib/api";

type Mode = "giris" | "kayit" | "dogrula" | "unuttum" | "reset-kod" | "yeni-sifre";

const TR_MAP: Record<string, string> = {
  ı: "i",
  ğ: "g",
  ü: "u",
  ş: "s",
  ö: "o",
  ç: "c",
  İ: "i",
  Ğ: "g",
  Ü: "u",
  Ş: "s",
  Ö: "o",
  Ç: "c",
};

function toUsername(value: string): string {
  return value
    .split("")
    .map((ch) => TR_MAP[ch] ?? ch)
    .join("")
    .toLowerCase()
    .replace(/[^a-z0-9_]/g, "")
    .slice(0, 24);
}

export function LoginScreen() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("giris");
  const [identifier, setIdentifier] = useState("");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [code, setCode] = useState("");
  const [mailOffline, setMailOffline] = useState(false);
  const [info, setInfo] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const biasRef = useRef(0);
  const rootRef = useRef<HTMLElement>(null);
  const progressRef = useRef(0);
  const [ready, setReady] = useState(false);
  const [scrollProgress, setScrollProgress] = useState(0);
  const onBiasChange = useCallback((v: number) => {
    biasRef.current = v;
  }, []);

  useEffect(() => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced) {
      setReady(true);
      return;
    }
    let inner = 0;
    const outer = window.requestAnimationFrame(() => {
      inner = window.requestAnimationFrame(() => setReady(true));
    });
    return () => {
      window.cancelAnimationFrame(outer);
      window.cancelAnimationFrame(inner);
    };
  }, []);

  useEffect(() => {
    const node = rootRef.current;
    if (!node) return;
    const onMove = (event: PointerEvent) => {
      node.style.setProperty("--mx", String(event.clientX / window.innerWidth));
      node.style.setProperty("--my", String(event.clientY / window.innerHeight));
    };
    window.addEventListener("pointermove", onMove, { passive: true });
    return () => window.removeEventListener("pointermove", onMove);
  }, []);

  const applyProgress = useCallback((delta: number) => {
    const next = Math.min(1, Math.max(0, progressRef.current + delta));
    if (next === progressRef.current) return;
    progressRef.current = next;
    setScrollProgress(next);
  }, []);

  useEffect(() => {
    const typing = (target: EventTarget | null) =>
      target instanceof HTMLInputElement ||
      target instanceof HTMLTextAreaElement ||
      target instanceof HTMLSelectElement;

    const onWheel = (event: WheelEvent) => {
      if (typing(event.target)) return;
      event.preventDefault();
      applyProgress(event.deltaY / 900);
    };

    const onKey = (event: KeyboardEvent) => {
      if (typing(event.target)) return;
      if (event.key === "ArrowDown" || event.key === "PageDown") {
        event.preventDefault();
        applyProgress(event.key === "PageDown" ? 0.22 : 0.1);
      }
      if (event.key === "ArrowUp" || event.key === "PageUp") {
        event.preventDefault();
        applyProgress(event.key === "PageUp" ? -0.22 : -0.1);
      }
    };

    let touchY = 0;
    const onTouchStart = (event: TouchEvent) => {
      if (typing(event.target) || (event.target as HTMLElement | null)?.closest(".login-card")) return;
      touchY = event.touches[0]?.clientY ?? 0;
    };
    const onTouchMove = (event: TouchEvent) => {
      if (typing(event.target) || (event.target as HTMLElement | null)?.closest(".login-card")) return;
      const y = event.touches[0]?.clientY ?? touchY;
      event.preventDefault();
      applyProgress((touchY - y) / 520);
      touchY = y;
    };

    window.addEventListener("wheel", onWheel, { passive: false, capture: true });
    window.addEventListener("keydown", onKey);
    window.addEventListener("touchstart", onTouchStart, { passive: true });
    window.addEventListener("touchmove", onTouchMove, { passive: false });
    return () => {
      window.removeEventListener("wheel", onWheel, { capture: true });
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("touchstart", onTouchStart);
      window.removeEventListener("touchmove", onTouchMove);
    };
  }, [applyProgress]);

  function go(next: Mode) {
    setMode(next);
    setError(null);
    setInfo(null);
    if (next === "giris" || next === "kayit" || next === "unuttum") {
      setPassword("");
      setPasswordConfirm("");
      setMailOffline(false);
      if (next !== "unuttum") setCode("");
    }
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      window.sessionStorage.setItem("hakim-scale-bias", String(biasRef.current));
      if (mode === "kayit") {
        if (password !== passwordConfirm) {
          setError("Şifreler eşleşmiyor.");
          return;
        }
        const pending = await registerAccount(username.trim(), email.trim(), password, username.trim());
        setIdentifier(username.trim());
        setMailOffline(!pending.mailed);
        setCode("");
        setMode("dogrula");
        setInfo(
          pending.mailed
            ? pending.message
            : "E-posta sunucusu bağlı değil. Kod iletilmedi.",
        );
        return;
      }
      if (mode === "dogrula") {
        await verifyAccount(identifier.trim(), code.trim());
        router.push("/arastirma");
        return;
      }
      if (mode === "unuttum") {
        const result = await requestPasswordReset(identifier.trim());
        setMailOffline(!result.mailed);
        setCode("");
        setPassword("");
        setPasswordConfirm("");
        setMode("reset-kod");
        setInfo(
          result.mailed
            ? result.message ?? "E-postanıza gönderilen kodu girin."
            : "E-posta sunucusu bağlı değil. Kod iletilmedi.",
        );
        return;
      }
      if (mode === "reset-kod") {
        if (!code.trim()) {
          setError("Kodu girin.");
          return;
        }
        setPassword("");
        setPasswordConfirm("");
        setMode("yeni-sifre");
        setInfo(null);
        return;
      }
      if (mode === "yeni-sifre") {
        if (password !== passwordConfirm) {
          setError("Şifreler eşleşmiyor.");
          return;
        }
        await resetPassword(identifier.trim(), code.trim(), password);
        setCode("");
        setPassword("");
        setPasswordConfirm("");
        setMode("giris");
        setInfo("Şifreniz güncellendi. Yeni şifrenizle giriş yapın.");
        return;
      }
      await loginAccount(identifier.trim(), password);
      router.push("/arastirma");
    } catch (err) {
      const message = err instanceof Error ? err.message : "İşlem başarısız";
      if (mode === "giris" && message.includes("doğrulama")) {
        setMode("dogrula");
        setInfo("Bu hesap için e-posta doğrulaması gerekli.");
      }
      setError(message);
    } finally {
      setLoading(false);
    }
  }

  async function onResend() {
    setLoading(true);
    setError(null);
    try {
      const result =
        mode === "reset-kod"
          ? await requestPasswordReset(identifier.trim())
          : await resendVerification(identifier.trim());
      setMailOffline(!result.mailed);
      setInfo(result.mailed ? "Yeni kod e-postanıza gönderildi." : "E-posta sunucusu bağlı değil. Kod iletilmedi.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Kod gönderilemedi");
    } finally {
      setLoading(false);
    }
  }

  const title =
    mode === "kayit"
      ? "Hesap Oluştur"
      : mode === "dogrula"
        ? "E-Posta Doğrulama"
        : mode === "unuttum"
          ? "Şifremi Unuttum"
          : mode === "reset-kod"
            ? "Sıfırlama Kodu"
            : mode === "yeni-sifre"
              ? "Yeni Şifre"
              : "Giriş";
  const slogan =
    mode === "kayit"
      ? "Kullanıcı adı ve e-posta ile kayıt. Aktivasyon kodundan sonra giriş yapılır."
      : mode === "dogrula"
        ? "E-postanıza gönderilen 6 haneli kodu girin."
        : mode === "unuttum"
          ? "Kullanıcı adı veya e-posta girin. Sıfırlama kodu e-postanıza gönderilir."
          : mode === "reset-kod"
            ? "E-postanıza gönderilen 6 haneli kodu girin."
            : mode === "yeni-sifre"
              ? "Yeni şifrenizi belirleyin ve tekrarını girin."
              : "Kullanıcı adı ve şifre ile giriş yapın.";

  const submitLabel = loading
    ? "İşleniyor…"
    : mode === "kayit"
      ? "Kayıt Ol"
      : mode === "dogrula"
        ? "Doğrula ve Gir"
        : mode === "unuttum"
          ? "Kod Gönder"
          : mode === "reset-kod"
            ? "Kodu Doğrula"
            : mode === "yeni-sifre"
              ? "Şifreyi Güncelle"
              : "Giriş Yap";

  const deep = scrollProgress > 0.12;

  return (
    <main
      ref={rootRef}
      className={ready ? "login-screen cinematic is-ready" : "login-screen cinematic"}
      data-scroll={deep ? "deep" : "hero"}
    >
      <div className="login-sticky">
        <div className="login-atmosphere" aria-hidden="true">
          <div className="login-depth" />
          <div className="login-vignette" />
          <div className="login-curtain" />
        </div>

        <div className="login-stage">
          <InteractiveScale onBiasChange={onBiasChange} size="hero" scrollProgress={scrollProgress} />
        </div>

        <header className="login-brand">
          <Image src="/hakim-emblem.png" alt="" width={28} height={28} priority />
          <span>HÂKİM</span>
        </header>

        <div className="login-titlecard">
          <p className="login-kicker">Kaynak Odaklı Hukuk Zekâsı</p>
          <p className="login-hero-copy">Kodun dili, geleceğin Hakimi.</p>
        </div>

      <section className="login-panel" aria-label="HÂKİM Giriş">
        <div className="login-card">
          <h2>{title}</h2>
          <p className="login-slogan">{slogan}</p>

          {mode === "giris" || mode === "kayit" ? (
            <div className="login-mode" data-mode={mode} role="tablist">
              <button type="button" className={mode === "giris" ? "active" : ""} onClick={() => go("giris")}>
                Giriş
              </button>
              <button type="button" className={mode === "kayit" ? "active" : ""} onClick={() => go("kayit")}>
                Kayıt Ol
              </button>
            </div>
          ) : null}

          <form className="login-form" onSubmit={onSubmit}>
            {mode === "kayit" ? (
              <>
                <label>
                  Kullanıcı Adı
                  <input
                    value={username}
                    onChange={(e) => setUsername(toUsername(e.target.value))}
                    placeholder="ornek_kullanici"
                    autoComplete="username"
                    required
                    minLength={3}
                    maxLength={24}
                    pattern="[a-z0-9_]{3,24}"
                    title="Küçük harf, rakam ve alt çizgi"
                  />
                </label>
                <label>
                  E-Posta
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="ornek@eposta.com"
                    autoComplete="email"
                    required
                  />
                </label>
              </>
            ) : null}
            {mode === "giris" || mode === "unuttum" ? (
              <label>
                Kullanıcı Adı
                <input
                  value={identifier}
                  onChange={(e) => setIdentifier(e.target.value)}
                  placeholder={mode === "unuttum" ? "ornek_kullanici veya e-posta" : "ornek_kullanici"}
                  autoComplete="username"
                  required
                />
              </label>
            ) : null}
            {mode === "dogrula" || mode === "reset-kod" ? (
              <>
                <label>
                  Kullanıcı Adı
                  <input value={identifier} onChange={(e) => setIdentifier(e.target.value)} required />
                </label>
                <label>
                  {mode === "reset-kod" ? "Sıfırlama Kodu" : "Doğrulama Kodu"}
                  <input
                    value={code}
                    onChange={(e) => setCode(e.target.value)}
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    placeholder="000000"
                    className="login-otp"
                    required
                  />
                </label>
                {mailOffline ? (
                  <p className="login-code-hint">E-posta sunucusu bağlı değil. Kod iletilmedi.</p>
                ) : null}
              </>
            ) : null}
            {mode === "giris" || mode === "kayit" || mode === "yeni-sifre" ? (
              <label>
                Şifre
                <PasswordInput
                  autoComplete={mode === "giris" ? "current-password" : "new-password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder={mode === "giris" ? "Şifreniz" : "En Az 6 Karakter"}
                  required
                  minLength={mode === "giris" ? 1 : 6}
                />
              </label>
            ) : null}
            {mode === "kayit" || mode === "yeni-sifre" ? (
              <label>
                Şifre Tekrarı
                <PasswordInput
                  autoComplete="new-password"
                  value={passwordConfirm}
                  onChange={(e) => setPasswordConfirm(e.target.value)}
                  placeholder="Şifreyi Tekrar Girin"
                  required
                  minLength={6}
                />
              </label>
            ) : null}
            {mode === "giris" ? (
              <button type="button" className="login-forgot" onClick={() => go("unuttum")}>
                Şifremi Unuttum
              </button>
            ) : null}
            {info ? <p className="login-info">{info}</p> : null}
            {error ? <p className="login-error">{error}</p> : null}
            <div className="login-actions">
              <button className="btn-gold" type="submit" disabled={loading}>
                {submitLabel}
              </button>
              {mode === "dogrula" || mode === "reset-kod" ? (
                <button className="btn-ghost" type="button" onClick={() => void onResend()} disabled={loading}>
                  Kodu Yeniden Gönder
                </button>
              ) : null}
              {mode === "dogrula" || mode === "unuttum" || mode === "reset-kod" ? (
                <button className="btn-ghost" type="button" onClick={() => go("giris")}>
                  Girişe Dön
                </button>
              ) : null}
            </div>
          </form>
        </div>
      </section>

        <p className="login-legal">HÂKİM · Kaynak odaklı hukuki araştırma</p>
        <button
          type="button"
          className="login-scroll-cue"
          aria-label="Sahneyi ilerlet"
          onClick={() => applyProgress(scrollProgress >= 0.96 ? -1 : 0.28)}
        >
          <span className="login-scroll-cue-label">Kanun · Vicdan</span>
          <span className="login-scroll-cue-chevron" aria-hidden="true" />
        </button>
      </div>
    </main>
  );
}
