"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import {
  AuthActivity,
  AuthUser,
  createAuthUser,
  getStoredUser,
  listAuthActivity,
  listAuthUsers,
} from "@/lib/api";

function when(value?: string | null) {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleString("tr-TR");
  } catch {
    return value;
  }
}

export function AdminConsole() {
  const router = useRouter();
  const [users, setUsers] = useState<AuthUser[]>([]);
  const [activity, setActivity] = useState<AuthActivity[]>([]);
  const [selected, setSelected] = useState("hepsi");
  const [error, setError] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [role, setRole] = useState<"user" | "admin">("user");
  const [saving, setSaving] = useState(false);

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

  const filtered = useMemo(
    () => (selected === "hepsi" ? activity : activity.filter((row) => row.user_id === selected)),
    [activity, selected],
  );

  async function onCreate(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await createAuthUser({
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
    } catch (err) {
      setError(err instanceof Error ? err.message : "Kullanıcı eklenemedi");
    } finally {
      setSaving(false);
    }
  }

  const selectedUser = users.find((item) => item.id === selected);

  return (
    <AppShell
      module="yonetim"
      sidebarTitle="Hesaplar"
      sidebarItems={[
        { id: "hepsi", label: "Tüm hareketler" },
        ...users.map((item) => ({
          id: item.id,
          label: `${item.display_name}${item.role === "admin" ? " (yönetici)" : ""}`,
        })),
      ]}
      sidebarActive={selected}
      onSidebarSelect={setSelected}
      quote="“Yönetici her oturumu görür; kullanıcı yalnız kendi işini görür.”"
      quoteMeta="Kalıcı hesap deposu · data/accounts.sqlite"
      inspectorTitle="Yeni kullanıcı"
      inspector={
        <form className="admin-create" onSubmit={onCreate}>
          <label>
            Ad
            <input value={displayName} onChange={(e) => setDisplayName(e.target.value)} required />
          </label>
          <label>
            Kullanıcı adı
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
            Parola
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} minLength={6} required />
          </label>
          <label>
            Rol
            <select value={role} onChange={(e) => setRole(e.target.value as "user" | "admin")}>
              <option value="user">Kullanıcı</option>
              <option value="admin">Yönetici</option>
            </select>
          </label>
          <button className="btn-gold" type="submit" disabled={saving}>
            {saving ? "Ekleniyor…" : "Hesap ekle"}
          </button>
        </form>
      }
      footer={error ? error : `${users.length} hesap · ${filtered.length} hareket`}
    >
      <section className="main-pane admin-pane">
        <div className="pane-hero">
          <h1>{selected === "hepsi" ? "Tüm kullanıcı hareketleri" : selectedUser?.display_name || "Hesap"}</h1>
          <p>
            {selected === "hepsi"
              ? "Giriş, kayıt, araştırma, evrak ve işlem kayıtları. Veriler sunucu kapanınca silinmez."
              : `${selectedUser?.username ? `@${selectedUser.username}` : selectedUser?.email} · son giriş ${when(selectedUser?.last_login_at)}`}
          </p>
        </div>
        {error ? <p className="login-error">{error}</p> : null}
        <div className="admin-users">
          {users.map((item) => (
            <button
              key={item.id}
              type="button"
              className={selected === item.id ? "active" : ""}
              onClick={() => setSelected(item.id)}
            >
              <strong>{item.display_name}</strong>
              <span>@{item.username || item.email}</span>
              <span>{item.role === "admin" ? "yönetici" : "kullanıcı"}</span>
            </button>
          ))}
        </div>
        <ul className="admin-activity">
          {filtered.length === 0 ? <li className="muted">Henüz hareket yok.</li> : null}
          {filtered.map((row) => (
            <li key={row.id}>
              <div>
                <strong>{row.display_name}</strong>
                <span>{row.email}</span>
                <span className="badge">{row.kind}</span>
              </div>
              <p>{row.summary}</p>
              <time>{when(row.created_at)}</time>
            </li>
          ))}
        </ul>
      </section>
    </AppShell>
  );
}
