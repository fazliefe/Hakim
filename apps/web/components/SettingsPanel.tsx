"use client";

import { FormEvent, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import {
  AuthUser,
  changeAccountPassword,
  confirmEmailChange,
  getCurrentUser,
  getStoredUser,
  requestEmailChange,
  revokeOwnSessions,
  updateAccountProfile,
} from "@/lib/api";
import { PasswordInput } from "@/components/PasswordInput";
import { HakimTheme, applyTheme, readTheme } from "@/lib/theme";

function when(value?: string | null) {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleString("tr-TR");
  } catch {
    return value;
  }
}

const SECTIONS = [
  { id: "gorunum", label: "Görünüm" },
  { id: "profil", label: "Profil" },
  { id: "eposta", label: "E-posta" },
  { id: "sifre", label: "Şifre" },
  { id: "oturum", label: "Oturumlar" },
] as const;

type SectionId = (typeof SECTIONS)[number]["id"];

export function SettingsPanel() {
  const [user, setUser] = useState<AuthUser | null>(getStoredUser());
  const [section, setSection] = useState<SectionId>("gorunum");
  const [theme, setTheme] = useState<HakimTheme>("dark");
  const [displayName, setDisplayName] = useState(getStoredUser()?.display_name || "");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [emailPassword, setEmailPassword] = useState("");
  const [newEmail, setNewEmail] = useState("");
  const [emailCode, setEmailCode] = useState("");
  const [mailOffline, setMailOffline] = useState(false);
  const [pendingEmail, setPendingEmail] = useState(false);
  const [info, setInfo] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [savingProfile, setSavingProfile] = useState(false);
  const [savingPassword, setSavingPassword] = useState(false);
  const [savingEmail, setSavingEmail] = useState(false);
  const [savingSessions, setSavingSessions] = useState(false);

  useEffect(() => {
    setTheme(readTheme());
    const onTheme = () => setTheme(readTheme());
    window.addEventListener("hakim-theme", onTheme);
    getCurrentUser()
      .then((next) => {
        setUser(next);
        setDisplayName(next.display_name || "");
        if (next.pending_email) setPendingEmail(true);
      })
      .catch(() => undefined);
    return () => window.removeEventListener("hakim-theme", onTheme);
  }, []);

  function flash(nextInfo: string | null, nextError: string | null = null) {
    setInfo(nextInfo);
    setError(nextError);
  }

  async function onProfile(event: FormEvent) {
    event.preventDefault();
    setSavingProfile(true);
    flash(null);
    try {
      const next = await updateAccountProfile(displayName.trim());
      setUser(next);
      flash("Görünen ad güncellendi.");
    } catch (err) {
      flash(null, err instanceof Error ? err.message : "Profil güncellenemedi");
    } finally {
      setSavingProfile(false);
    }
  }

  async function onPassword(event: FormEvent) {
    event.preventDefault();
    if (newPassword !== passwordConfirm) {
      flash(null, "Yeni şifreler eşleşmiyor.");
      return;
    }
    setSavingPassword(true);
    flash(null);
    try {
      const next = await changeAccountPassword(currentPassword, newPassword);
      setUser(next);
      setCurrentPassword("");
      setNewPassword("");
      setPasswordConfirm("");
      flash("Parola güncellendi. Diğer oturumlar kapatıldı.");
    } catch (err) {
      flash(null, err instanceof Error ? err.message : "Parola güncellenemedi");
    } finally {
      setSavingPassword(false);
    }
  }

  async function onEmailRequest(event: FormEvent) {
    event.preventDefault();
    setSavingEmail(true);
    flash(null);
    try {
      const result = await requestEmailChange(emailPassword, newEmail.trim());
      setPendingEmail(true);
      setMailOffline(!result.mailed);
      flash(
        result.mailed
          ? result.message ?? "Onay kodu gönderildi."
          : "E-posta sunucusu bağlı değil. Kod iletilmedi.",
      );
    } catch (err) {
      flash(null, err instanceof Error ? err.message : "E-posta güncellenemedi");
    } finally {
      setSavingEmail(false);
    }
  }

  async function onEmailConfirm(event: FormEvent) {
    event.preventDefault();
    setSavingEmail(true);
    flash(null);
    try {
      const next = await confirmEmailChange(emailCode.trim());
      setUser(next);
      setPendingEmail(false);
      setMailOffline(false);
      setNewEmail("");
      setEmailPassword("");
      setEmailCode("");
      flash("E-posta güncellendi.");
    } catch (err) {
      flash(null, err instanceof Error ? err.message : "E-posta doğrulanamadı");
    } finally {
      setSavingEmail(false);
    }
  }

  async function onRevokeSessions() {
    setSavingSessions(true);
    flash(null);
    try {
      const result = await revokeOwnSessions();
      setUser(result.user);
      flash(`${result.revoked} diğer oturum kapatıldı. Bu tarayıcıdaki oturum açık kaldı.`);
    } catch (err) {
      flash(null, err instanceof Error ? err.message : "Oturumlar kapatılamadı");
    } finally {
      setSavingSessions(false);
    }
  }

  return (
    <AppShell
      module="ayarlar"
      sidebarTitle="Ayarlar"
      sidebarItems={SECTIONS.map((item) => ({ id: item.id, label: item.label }))}
      sidebarActive={section}
      onSidebarSelect={(id) => setSection(id as SectionId)}
      quote="“Hesap bilgileri yalnızca sizin oturumunuzdan güncellenir.”"
      quoteMeta="Ayarlar · profil, e-posta, şifre, oturum"
      inspectorTitle="Hesap Özeti"
      inspector={
        <div className="settings-meta">
          <p>
            <strong>{user?.display_name || "—"}</strong>
          </p>
          <p>@{user?.username || "—"}</p>
          <p>{user?.email}</p>
          <p>{user?.role === "admin" ? "Yönetici" : "Kullanıcı"}</p>
          <p>{user?.email_verified ? "E-Posta Doğrulanmış" : "Doğrulama Bekliyor"}</p>
          <p>Son giriş: {when(user?.last_login_at)}</p>
        </div>
      }
      footer={info || error || "Değişiklikler hesap veritabanına yazılır."}
    >
      <section className="main-pane settings-pane">
        <div className="pane-hero">
          <h1>Ayarlar</h1>
          <p>Görünüm, profil, e-posta, şifre ve oturumları buradan yönetin. Kullanıcı adı sabit kalır.</p>
        </div>
        {error ? <p className="login-error">{error}</p> : null}
        {info ? <p className="login-info">{info}</p> : null}

        <div className="settings-grid">
          {section === "gorunum" ? (
            <div className="settings-card">
              <h2>Görünüm</h2>
              <p className="muted">Çalışma masası açık veya koyu tema kullanır. Giriş sahnesi koyu kalır.</p>
              <div className="theme-choice">
                <button
                  type="button"
                  className={theme === "light" ? "active" : ""}
                  onClick={() => {
                    applyTheme("light");
                    setTheme("light");
                  }}
                >
                  Açık
                </button>
                <button
                  type="button"
                  className={theme === "dark" ? "active" : ""}
                  onClick={() => {
                    applyTheme("dark");
                    setTheme("dark");
                  }}
                >
                  Koyu
                </button>
              </div>
            </div>
          ) : null}

          {section === "profil" ? (
            <form className="settings-card" onSubmit={onProfile}>
              <h2>Profil</h2>
              <label>
                Kullanıcı Adı
                <input value={user?.username || ""} readOnly />
              </label>
              <label>
                Görünen Ad
                <input
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  minLength={2}
                  maxLength={80}
                  required
                />
              </label>
              <p className="muted">
                Rol: {user?.role === "admin" ? "Yönetici" : "Kullanıcı"} · Kayıt {when(user?.created_at)}
              </p>
              <button className="btn-gold" type="submit" disabled={savingProfile}>
                {savingProfile ? "Kaydediliyor…" : "Profili Kaydet"}
              </button>
            </form>
          ) : null}

          {section === "eposta" ? (
            <form className="settings-card" onSubmit={pendingEmail ? onEmailConfirm : onEmailRequest}>
              <h2>E-posta</h2>
              <p className="muted">Mevcut Adres: {user?.email}</p>
              {user?.pending_email ? <p className="muted">Bekleyen Adres: {user.pending_email}</p> : null}
              {pendingEmail ? (
                <>
                  <label>
                    Onay Kodu
                    <input
                      value={emailCode}
                      onChange={(e) => setEmailCode(e.target.value)}
                      inputMode="numeric"
                      autoComplete="one-time-code"
                      placeholder="000000"
                      required
                    />
                  </label>
                  {mailOffline ? (
                    <p className="login-code-hint">E-posta sunucusu bağlı değil. Kod iletilmedi.</p>
                  ) : null}
                  <button className="btn-gold" type="submit" disabled={savingEmail}>
                    {savingEmail ? "Doğrulanıyor…" : "Kodu Doğrula"}
                  </button>
                </>
              ) : (
                <>
                  <label>
                    Yeni E-Posta
                    <input
                      type="email"
                      value={newEmail}
                      onChange={(e) => setNewEmail(e.target.value)}
                      autoComplete="email"
                      required
                    />
                  </label>
                  <label>
                    Mevcut Şifre
                    <PasswordInput
                      value={emailPassword}
                      onChange={(e) => setEmailPassword(e.target.value)}
                      autoComplete="current-password"
                      required
                    />
                  </label>
                  <button className="btn-gold" type="submit" disabled={savingEmail}>
                    {savingEmail ? "Kod Gönderiliyor…" : "Doğrulama Kodu Gönder"}
                  </button>
                </>
              )}
            </form>
          ) : null}

          {section === "sifre" ? (
            <form className="settings-card" onSubmit={onPassword}>
              <h2>Şifre</h2>
              <label>
                Mevcut Şifre
                <PasswordInput
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  autoComplete="current-password"
                  required
                />
              </label>
              <label>
                Yeni Şifre
                <PasswordInput
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  autoComplete="new-password"
                  minLength={6}
                  required
                />
              </label>
              <label>
                Yeni Şifre Tekrarı
                <PasswordInput
                  value={passwordConfirm}
                  onChange={(e) => setPasswordConfirm(e.target.value)}
                  autoComplete="new-password"
                  minLength={6}
                  required
                />
              </label>
              <button className="btn-gold" type="submit" disabled={savingPassword}>
                {savingPassword ? "Kaydediliyor…" : "Şifreyi Güncelle"}
              </button>
            </form>
          ) : null}

          {section === "oturum" ? (
            <div className="settings-card">
              <h2>Oturumlar</h2>
              <p>Açık oturum: {user?.session_count ?? 0}</p>
              <p className="muted">
                Diğer cihazlardaki oturumları kapatır. Bu tarayıcıdaki giriş açık kalır. Çıkış için sağ üstteki
                Ayarlar menüsünü kullanın.
              </p>
              <button className="btn-gold" type="button" disabled={savingSessions} onClick={() => void onRevokeSessions()}>
                {savingSessions ? "Kapatılıyor…" : "Diğer Oturumları Kapat"}
              </button>
            </div>
          ) : null}
        </div>
      </section>
    </AppShell>
  );
}
