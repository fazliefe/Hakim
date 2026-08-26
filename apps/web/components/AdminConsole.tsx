"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { PasswordInput } from "@/components/PasswordInput";
import {
  AuthActivity,
  AuthUser,
  createAuthUser,
  deleteAuthUser,
  getStoredUser,
  listAuthActivity,
  listAuthUsers,
  patchAuthUser,
  revokeAuthSessions,
  sendAuthPassword,
} from "@/lib/api";

function when(value?: string | null) {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleString("tr-TR");
  } catch {
    return value;
  }
}

function logWhen(value?: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(date.getDate())}.${pad(date.getMonth() + 1)}.${date.getFullYear()} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

const ACTIVITY_TITLES: Record<string, string> = {
  register: "Yeni Hesap Açıldı",
  login: "Başarılı Giriş Yapıldı",
  verify: "E-Posta Doğrulandı",
  password_reset_request: "Parola Sıfırlama İstendi",
  password_reset: "Parola Sıfırlandı",
  password_change: "Parola Değiştirildi",
  email_change_request: "E-Posta Değişikliği İstendi",
  email_change: "E-Posta Değiştirildi",
  profile_update: "Profil Güncellendi",
  session_revoke: "Oturumlar Kapatıldı",
  admin_create_user: "Yeni Hesap Oluşturuldu",
  admin_set_role: "Rol Değiştirildi",
  admin_lock: "Hesap Kilitlendi",
  admin_unlock: "Hesap Kilidi Açıldı",
  admin_delete_user: "Hesap Silindi",
  admin_revoke_sessions: "Oturumlar Yönetici Tarafından Kapatıldı",
  admin_send_password: "Geçici Parola E-Posta ile Gönderildi",
};

function activityTitle(row: AuthActivity) {
  if (row.kind === "login" && row.role === "admin") {
    return "Yönetici Paneline Başarılı Giriş Yapıldı";
  }
  return ACTIVITY_TITLES[row.kind] || row.summary;
}

function activityTarget(row: AuthActivity) {
  const handle = row.username || row.user_id;
  return row.role === "admin" ? `admin_user / ${handle}` : `user / ${handle}`;
}

function activityRole(role?: string) {
  return role === "admin" ? "Yönetici - Tam Yetkili" : "Kullanıcı";
}

function activityReason(row: AuthActivity) {
  const text = (row.summary || activityTitle(row)).trim();
  return /[.!?…]$/.test(text) ? text : `${text}.`;
}

function HistoryIcon() {
  return (
    <svg className="admin-log-icon" viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M13.2 4.2a8 8 0 1 0 6.9 4.4"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
      <path
        d="M20.6 3.6v4.2h-4.2"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M12 8.4v4.1l2.7 1.6"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

const ACCOUNT_ACTIVITY_KINDS = new Set([
  "register",
  "login",
  "verify",
  "password_reset_request",
  "password_reset",
  "password_change",
  "email_change_request",
  "email_change",
  "profile_update",
  "session_revoke",
  "admin_create_user",
  "admin_set_role",
  "admin_lock",
  "admin_unlock",
  "admin_delete_user",
  "admin_revoke_sessions",
  "admin_send_password",
]);

function initials(value?: string) {
  const parts = (value || "H").trim().split(/\s+/).filter(Boolean);
  const first = parts[0]?.[0] || "H";
  const second = parts[1]?.[0] || parts[0]?.[1] || "";
  return (first + second).toUpperCase();
}

function statusLabel(user: AuthUser) {
  if (user.locked) return "Kilitli";
  if (!user.email_verified) return "Davet Bekliyor";
  return "Aktif";
}

export function AdminConsole() {
  const router = useRouter();
  const params = useSearchParams();
  const self = getStoredUser();
  const [users, setUsers] = useState<AuthUser[]>([]);
  const [activity, setActivity] = useState<AuthActivity[]>([]);
  const selected = params.get("hesap") || "hepsi";
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [role, setRole] = useState<"user" | "admin">("user");
  const [saving, setSaving] = useState(false);
  const [busy, setBusy] = useState(false);

  async function reload() {
    const [nextUsers, nextActivity] = await Promise.all([listAuthUsers(), listAuthActivity()]);
    setUsers(nextUsers);
    setActivity(nextActivity);
  }

  useEffect(() => {
    if (getStoredUser()?.role !== "admin") {
      router.replace("/arastirma");
      return;
    }
    reload().catch((err: unknown) => {
      setError(err instanceof Error ? err.message : "Yönetim paneli yüklenemedi");
    });
  }, [router]);

  function selectAccount(id: string) {
    const next = id === "hepsi" ? "/yonetim" : `/yonetim?hesap=${encodeURIComponent(id)}`;
    if (id === selected) return;
    if (id === "hepsi" || selected === "hepsi") {
      router.push(next);
      return;
    }
    router.replace(next);
  }

  const recent = useMemo(() => {
    const rows = (selected === "hepsi" ? activity : activity.filter((row) => row.user_id === selected)).filter(
      (row) => ACCOUNT_ACTIVITY_KINDS.has(row.kind),
    );
    return rows.slice(0, 24);
  }, [activity, selected]);
  const selectedUser = users.find((item) => item.id === selected);
  const isSelf = selectedUser?.id === self?.id;
  const adminCount = users.filter((item) => item.role === "admin").length;
  const lockedCount = users.filter((item) => item.locked).length;
  const pendingCount = users.filter((item) => !item.email_verified).length;

  async function onCreate(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setInfo(null);
    try {
      const created = await createAuthUser({
        username: username.trim().toLowerCase(),
        email: email.trim(),
        password,
        display_name: displayName.trim(),
        role,
      });
      setEmail("");
      setPassword("");
      setDisplayName("");
      setUsername("");
      setRole("user");
      await reload();
      setInfo(
        created.mailed
          ? created.message || "Hesap oluşturuldu."
          : (created.message || "Hesap oluşturuldu.") + " E-posta sunucusu bağlı değil. Kod iletilmedi.",
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Kullanıcı eklenemedi");
    } finally {
      setSaving(false);
    }
  }

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError(null);
    setInfo(null);
    try {
      await action();
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "İşlem başarısız");
    } finally {
      setBusy(false);
    }
  }

  async function onRole(next: "admin" | "user") {
    if (!selectedUser) return;
    await run(async () => {
      await patchAuthUser(selectedUser.id, { role: next });
      setInfo(`Rol güncellendi: ${selectedUser.username} -> ${next}`);
    });
  }

  async function onLock() {
    if (!selectedUser) return;
    const nextLocked = !selectedUser.locked;
    await run(async () => {
      await patchAuthUser(selectedUser.id, { locked: nextLocked });
      setInfo(nextLocked ? "Hesap kilitlendi." : "Hesap kilidi açıldı.");
    });
  }

  async function onRevoke() {
    if (!selectedUser) return;
    await run(async () => {
      const count = await revokeAuthSessions(selectedUser.id);
      setInfo(`${count} oturum kapatıldı.`);
    });
  }

  async function onSendPassword() {
    if (!selectedUser) return;
    if (
      !window.confirm(
        `${selectedUser.username} için yeni geçici parola oluşturulup e-postaya gönderilecek. Mevcut parola geçersiz olur.`,
      )
    ) {
      return;
    }
    await run(async () => {
      const result = await sendAuthPassword(selectedUser.id);
      setInfo(
        result.mailed
          ? result.message || "Parola e-postaya gönderildi."
          : (result.message || "Parola oluşturuldu.") + " E-posta sunucusu bağlı değil. Parola iletilmedi.",
      );
    });
  }

  async function onDelete() {
    if (!selectedUser) return;
    if (!window.confirm(`${selectedUser.username} hesabını silmek istiyor musunuz? Bu işlem geri alınamaz.`)) {
      return;
    }
    await run(async () => {
      await deleteAuthUser(selectedUser.id);
      router.replace("/yonetim");
      setInfo("Hesap silindi.");
    });
  }

  return (
    <AppShell
      module="yonetim"
      sidebarTitle="Kullanıcılar"
      sidebarItems={[
        { id: "hepsi", label: "Tüm Hesaplar" },
        ...users.map((item) => ({
          id: item.id,
          label: `${item.display_name}${item.locked ? " (kilitli)" : item.role === "admin" ? " (yönetici)" : ""}`,
        })),
      ]}
      sidebarActive={selected}
      onSidebarSelect={selectAccount}
      quote="“Yetki görünür olmalı; dosya değil, masa.”"
      quoteMeta="Yönetim Masası · data/accounts.sqlite"
      inspectorTitle="Davet"
      inspector={
        <div className="admin-inspector">
          <form className="admin-create" onSubmit={onCreate}>
            <p className="admin-invite-note">Yeni hesap e-posta doğrulaması olmadan açılmaz.</p>
            <label>
              Ad
              <input value={displayName} onChange={(e) => setDisplayName(e.target.value)} required />
            </label>
            <label>
              Kullanıcı Adı
              <input
                value={username}
                onChange={(e) => setUsername(e.target.value.toLowerCase())}
                placeholder="ornek_kullanici"
                required
                minLength={3}
              />
            </label>
            <label>
              E-posta
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="ornek@eposta.com" required />
            </label>
            <label>
              Geçici Parola
              <PasswordInput value={password} onChange={(e) => setPassword(e.target.value)} minLength={6} required />
            </label>
            <label>
              Rol
              <select value={role} onChange={(e) => setRole(e.target.value as "user" | "admin")}>
                <option value="user">Kullanıcı</option>
                <option value="admin">Yönetici</option>
              </select>
            </label>
            <button className="btn-gold" type="submit" disabled={saving}>
              {saving ? "Ekleniyor…" : "Davet Gönder"}
            </button>
          </form>
          <div className="admin-recent">
            <h3>{selected === "hepsi" ? "Son İşlemler" : "Bu Hesabın İşlemleri"}</h3>
            {recent.length === 0 ? <p className="muted">Henüz hareket yok.</p> : null}
            <ul>
              {recent.map((row) => (
                <li key={row.id}>
                  <article className="admin-log-card">
                    <header className="admin-log-head">
                      <HistoryIcon />
                      <h4>{activityTitle(row)}</h4>
                    </header>
                    <dl className="admin-log-fields">
                      <div>
                        <dt>Hedef:</dt>
                        <dd>{activityTarget(row)}</dd>
                      </div>
                      <div>
                        <dt>İşlemi yapan:</dt>
                        <dd>{row.display_name || "—"}</dd>
                      </div>
                      <div>
                        <dt>E-posta:</dt>
                        <dd>{row.email || "—"}</dd>
                      </div>
                      <div>
                        <dt>Rol:</dt>
                        <dd>{activityRole(row.role)}</dd>
                      </div>
                      <div>
                        <dt>Tarih:</dt>
                        <dd>{logWhen(row.created_at)}</dd>
                      </div>
                      <div>
                        <dt>Sebep:</dt>
                        <dd>{activityReason(row)}</dd>
                      </div>
                    </dl>
                  </article>
                </li>
              ))}
            </ul>
          </div>
        </div>
      }
      footer={error ? error : info ? info : `${users.length} hesap · yönetim masası`}
    >
      <section className="main-pane admin-pane">
        <header className="admin-hero">
          <p className="admin-kicker">Yönetim Masası</p>
          <h1>{selected === "hepsi" ? "Hesaplar" : selectedUser?.display_name || "Hesap"}</h1>
          <p className="admin-lede">
            {selected === "hepsi"
              ? "Karttan seç, sağdan davet et. Yetki bu masadan yürür."
              : `${selectedUser?.username ? `@${selectedUser.username}` : selectedUser?.email} · son giriş ${when(selectedUser?.last_login_at)}`}
          </p>
          {selected === "hepsi" ? (
            <div className="admin-stats">
              <span>
                <strong>{users.length}</strong>
                hesap
              </span>
              <span>
                <strong>{adminCount}</strong>
                yönetici
              </span>
              <span>
                <strong>{lockedCount}</strong>
                kilitli
              </span>
              <span>
                <strong>{pendingCount}</strong>
                davet
              </span>
            </div>
          ) : null}
        </header>
        {error ? <p className="login-error">{error}</p> : null}
        {info ? <p className="login-info">{info}</p> : null}

        {selected === "hepsi" ? (
          <div className="admin-users">
            {users.map((item) => (
              <button
                key={item.id}
                type="button"
                className={[
                  item.role === "admin" ? "is-admin" : "",
                  item.locked ? "is-locked" : "",
                ]
                  .filter(Boolean)
                  .join(" ")}
                onClick={() => selectAccount(item.id)}
              >
                <span className="admin-mono">{initials(item.display_name)}</span>
                <span className="admin-person">
                  <strong>{item.display_name}</strong>
                  <em>@{item.username || item.email}</em>
                </span>
                <span className="admin-chips">
                  <i className={item.role === "admin" ? "chip-gold" : ""}>{item.role === "admin" ? "Yönetici" : "Kullanıcı"}</i>
                  <i className={item.locked ? "chip-warn" : item.email_verified ? "chip-ok" : "chip-wait"}>
                    {statusLabel(item)}
                  </i>
                </span>
              </button>
            ))}
          </div>
        ) : selectedUser ? (
          <article className={`admin-dossier${selectedUser.locked ? " is-locked" : ""}${selectedUser.role === "admin" ? " is-admin" : ""}`}>
            <div className="admin-dossier-head">
              <span className="admin-mono xl">{initials(selectedUser.display_name)}</span>
              <div>
                <p className="admin-kicker">{selectedUser.role === "admin" ? "Yönetici Dosyası" : "Kullanıcı Dosyası"}</p>
                <h2>{selectedUser.display_name}</h2>
                <p>@{selectedUser.username}</p>
              </div>
            </div>
            <div className="admin-metrics">
              <div>
                <span>E-posta</span>
                <strong>{selectedUser.email}</strong>
              </div>
              <div>
                <span>Durum</span>
                <strong>{statusLabel(selectedUser)}</strong>
              </div>
              <div>
                <span>Açık Oturum</span>
                <strong>{selectedUser.session_count ?? 0}</strong>
              </div>
              <div>
                <span>Kayıt</span>
                <strong>{when(selectedUser.created_at)}</strong>
              </div>
            </div>
            <div className="admin-actions">
              <label>
                Rol
                <select
                  value={selectedUser.role}
                  disabled={busy || isSelf}
                  onChange={(e) => void onRole(e.target.value as "admin" | "user")}
                >
                  <option value="user">Kullanıcı</option>
                  <option value="admin">Yönetici</option>
                </select>
              </label>
              <button type="button" className="btn-ghost" disabled={busy || isSelf} onClick={() => void onLock()}>
                {selectedUser.locked ? "Kilidi Aç" : "Kilitle"}
              </button>
              <button type="button" className="btn-ghost" disabled={busy} onClick={() => void onSendPassword()}>
                Şifreyi E-Posta ile Gönder
              </button>
              <button type="button" className="btn-ghost" disabled={busy} onClick={() => void onRevoke()}>
                Oturumları Kapat
              </button>
              <button type="button" className="btn-ghost danger" disabled={busy || isSelf} onClick={() => void onDelete()}>
                Hesabı Sil
              </button>
            </div>
            {isSelf ? (
              <p className="muted">Kendi hesabınızı kilitleyemez veya silemezsiniz. Şifre ve e-posta Ayarlar menüsünde.</p>
            ) : null}
          </article>
        ) : null}
      </section>
    </AppShell>
  );
}
