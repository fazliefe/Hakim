"use client";

import Image from "next/image";
import { FormEvent, useCallback, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { InteractiveScale } from "@/components/InteractiveScale";
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
  const [previewCode, setPreviewCode] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const biasRef = useRef(0);
  const onBiasChange = useCallback((v: number) => {
    biasRef.current = v;
  }, []);

  function go(next: Mode) {
    setMode(next);
    setError(null);
    setInfo(null);
    if (next === "giris" || next === "kayit" || next === "unuttum") {
      setPassword("");
      setPasswordConfirm("");
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
        setPreviewCode(pending.preview_code ?? null);
        setCode(pending.preview_code ?? "");
        setMode("dogrula");
        setInfo(pending.message);
        return;
      }
      if (mode === "dogrula") {
        await verifyAccount(identifier.trim(), code.trim());
        router.push("/arastirma");
        return;
      }
      if (mode === "unuttum") {
        const result = await requestPasswordReset(identifier.trim());
        setPreviewCode(result.preview_code ?? null);
        setCode(result.preview_code ?? "");
        setPassword("");
        setPasswordConfirm("");
        setMode("reset-kod");
        setInfo(result.message ?? "E-postanıza gönderilen kodu girin.");
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
        setPreviewCode(null);
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
      setPreviewCode(result.preview_code ?? null);
      setInfo(result.mailed ? "Yeni kod e-postanıza gönderildi." : "Yeni kod oluşturuldu.");
      if (result.preview_code) setCode(result.preview_code);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Kod gönderilemedi");
    } finally {
      setLoading(false);
    }
  }

  const title =
    mode === "kayit"
      ? "Hesap oluştur"
      : mode === "dogrula"
        ? "E-posta doğrulama"
        : mode === "unuttum"
          ? "Şifremi unuttum"
          : mode === "reset-kod"
            ? "Sıfırlama kodu"
            : mode === "yeni-sifre"
              ? "Yeni şifre"
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
      ? "Kayıt ol"
      : mode === "dogrula"
        ? "Doğrula ve gir"
        : mode === "unuttum"
          ? "Kod gönder"
          : mode === "reset-kod"
            ? "Kodu doğrula"
            : mode === "yeni-sifre"
              ? "Şifreyi güncelle"
              : "Giriş yap";

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
          <h2>{title}</h2>
          <p className="login-slogan">{slogan}</p>

          {mode === "giris" || mode === "kayit" ? (
            <div className="login-mode" role="tablist">
              <button type="button" className={mode === "giris" ? "active" : ""} onClick={() => go("giris")}>
                Giriş
              </button>
              <button type="button" className={mode === "kayit" ? "active" : ""} onClick={() => go("kayit")}>
                Kayıt ol
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
                Kullanıcı adı
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
                  Kullanıcı adı
                  <input value={identifier} onChange={(e) => setIdentifier(e.target.value)} required />
                </label>
                <label>
                  {mode === "reset-kod" ? "Sıfırlama kodu" : "Doğrulama kodu"}
                  <input
                    value={code}
                    onChange={(e) => setCode(e.target.value)}
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    placeholder="000000"
                    required
                  />
                </label>
                {previewCode ? (
                  <p className="login-code-hint">
                    E-posta sunucusu bağlı değil. Kod: <strong>{previewCode}</strong>
                  </p>
                ) : null}
              </>
            ) : null}
            {mode === "giris" || mode === "kayit" || mode === "yeni-sifre" ? (
              <label>
                Şifre
                <input
                  type="password"
                  autoComplete={mode === "giris" ? "current-password" : "new-password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder={mode === "giris" ? "Şifreniz" : "Şifrenizi oluşturun"}
                  required
                  minLength={6}
                />
              </label>
            ) : null}
            {mode === "kayit" || mode === "yeni-sifre" ? (
              <label>
                Şifre Tekrarı
                <input
                  type="password"
                  autoComplete="new-password"
                  value={passwordConfirm}
                  onChange={(e) => setPasswordConfirm(e.target.value)}
                  placeholder="Şifreyi tekrar girin"
                  required
                  minLength={6}
                />
              </label>
            ) : null}
            {mode === "giris" ? (
              <button type="button" className="login-forgot" onClick={() => go("unuttum")}>
                Şifremi unuttum
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
                  Kodu yeniden gönder
                </button>
              ) : null}
              {mode === "dogrula" || mode === "unuttum" || mode === "reset-kod" ? (
                <button className="btn-ghost" type="button" onClick={() => go("giris")}>
                  Girişe dön
                </button>
              ) : null}
            </div>
          </form>
        </div>
      </section>
    </main>
  );
}
