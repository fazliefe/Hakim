"use client";

import Image from "next/image";
import Link from "next/link";
import { CSSProperties, PointerEvent, ReactNode, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { SystemStatus, getStoredUser, getSystemStatus, isLiveCheck, logoutAccount, type AuthUser } from "@/lib/api";

const OFFLINE_STATUS: SystemStatus = {
  status: "kapalı",
  service: "hakim-api",
  ready: false,
  checks: { api: "kapalı", elasticsearch: "kapalı", neo4j: "kapalı", postgres: "kapalı", yazim: "kapalı" },
};

const STATUS_POLL_MS = 8000;
const STATUS_TIMEOUT_MS = 4000;
const INSPECTOR_MIN = 240;
const INSPECTOR_MAX = 560;
const INSPECTOR_DEFAULT = 340;
const NAV_MIN = 176;
const NAV_MAX = 420;
const NAV_DEFAULT = 232;

const CHECK_LABELS: Array<[keyof SystemStatus["checks"], string]> = [
  ["api", "API"],
  ["elasticsearch", "Arama"],
  ["neo4j", "Graf"],
  ["postgres", "Arşiv"],
  ["yazim", "Yazım"],
];

const MODULES = [
  { href: "/arastirma", id: "arastirma", label: "Araştırma" },
  { href: "/evrak", id: "evrak", label: "Evrak" },
  { href: "/islem", id: "islem", label: "Dilekçe" },
] as const;

export type HakimModule = (typeof MODULES)[number]["id"] | "yonetim" | "ayarlar" | "kamu" | "surec";
export type InspectorMode = "open" | "collapsed" | "hidden";

export type SidebarItem = {
  id: string;
  label: string;
};

export type SidebarSection = {
  title?: string;
  items: SidebarItem[];
};

export function AppShell({
  module,
  sidebarTitle,
  sidebarItems,
  sidebarSections,
  sidebarActive,
  onSidebarSelect,
  quote,
  quoteMeta,
  inspectorTitle,
  inspector,
  inspectorMode = "open",
  onInspectorModeChange,
  footer,
  hideStatusBar,
  children,
}: {
  module: HakimModule;
  sidebarTitle: string;
  sidebarItems?: SidebarItem[];
  sidebarSections?: SidebarSection[];
  sidebarActive: string;
  onSidebarSelect: (id: string) => void;
  quote?: string;
  quoteMeta?: string;
  inspectorTitle?: string;
  inspector?: ReactNode;
  inspectorMode?: InspectorMode;
  onInspectorModeChange?: (mode: InspectorMode) => void;
  footer?: string;
  hideStatusBar?: boolean;
  children: ReactNode;
}) {
  const router = useRouter();
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [inspectorWidth, setInspectorWidth] = useState(INSPECTOR_DEFAULT);
  const [navWidth, setNavWidth] = useState(NAV_DEFAULT);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const dragRef = useRef<{ kind: "nav" | "inspector"; startX: number; startW: number } | null>(null);

  useEffect(() => {
    setUser(getStoredUser());
    const onAuth = () => setUser(getStoredUser());
    window.addEventListener("hakim-auth-updated", onAuth);
    let cancelled = false;
    let inFlight: AbortController | null = null;
    let seq = 0;
    const load = () => {
      inFlight?.abort();
      const my = ++seq;
      const controller = new AbortController();
      inFlight = controller;
      const timeout = window.setTimeout(() => controller.abort(), STATUS_TIMEOUT_MS);
      getSystemStatus(controller.signal)
        .then((data) => {
          if (!cancelled && my === seq) setStatus(data);
        })
        .catch(() => {
          if (!cancelled && my === seq) setStatus(OFFLINE_STATUS);
        })
        .finally(() => window.clearTimeout(timeout));
    };
    load();
    const timer = window.setInterval(load, STATUS_POLL_MS);
    const onPointer = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMenuOpen(false);
    };
    window.addEventListener("mousedown", onPointer);
    window.addEventListener("keydown", onKey);
    return () => {
      cancelled = true;
      inFlight?.abort();
      window.clearInterval(timer);
      window.removeEventListener("hakim-auth-updated", onAuth);
      window.removeEventListener("mousedown", onPointer);
      window.removeEventListener("keydown", onKey);
    };
  }, []);

  async function logout() {
    setMenuOpen(false);
    await logoutAccount();
    router.push("/giris");
  }

  function onResizeStart(kind: "nav" | "inspector", event: PointerEvent<HTMLButtonElement>) {
    event.preventDefault();
    dragRef.current = {
      kind,
      startX: event.clientX,
      startW: kind === "nav" ? navWidth : inspectorWidth,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function onResizeMove(event: PointerEvent<HTMLButtonElement>) {
    if (!dragRef.current) return;
    const delta = event.clientX - dragRef.current.startX;
    if (dragRef.current.kind === "nav") {
      setNavWidth(Math.min(NAV_MAX, Math.max(NAV_MIN, dragRef.current.startW + delta)));
      return;
    }
    setInspectorWidth(Math.min(INSPECTOR_MAX, Math.max(INSPECTOR_MIN, dragRef.current.startW - delta)));
  }

  function onResizeEnd() {
    dragRef.current = null;
  }

  const navSections =
    sidebarSections ??
    (sidebarItems ? [{ items: sidebarItems }] : []);
  const showInspector = inspectorMode === "open";

  return (
    <div className={`app-shell${hideStatusBar ? " no-status" : ""}`} data-module={module}>
      <header className="topbar">
        <Link href="/arastirma" className="brand-lockup" aria-label="HÂKİM ana sayfa">
          <Image src="/hakim-emblem.png" alt="" width={36} height={36} />
          <strong>HÂKİM</strong>
        </Link>
        <nav className="module-nav" aria-label="Modüller">
          {MODULES.map((item) => (
            <Link
              key={item.id}
              href={item.href}
              className={module === item.id ? "active" : ""}
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="topbar-actions">
          <div className="system-pills compact" aria-label="Sistem durumu">
            {CHECK_LABELS.map(([key, label]) => {
              const ok = isLiveCheck(status?.checks[key]);
              return (
                <span key={key} className={`sys-pill ${ok ? "ok" : "down"}`}>
                  <i />
                  {label}
                </span>
              );
            })}
          </div>
          <div className="account-menu" ref={menuRef}>
            <button
              type="button"
              className={`account-menu-toggle${menuOpen || module === "ayarlar" || module === "yonetim" ? " open" : ""}`}
              aria-expanded={menuOpen}
              aria-haspopup="menu"
              onClick={() => setMenuOpen((open) => !open)}
            >
              Ayarlar
            </button>
            {menuOpen ? (
              <div className="account-menu-panel" role="menu">
                <p className="account-menu-user">
                  <strong>{user?.display_name || "Hesap"}</strong>
                  <span>@{user?.username || "—"}</span>
                </p>
                <Link href="/ayarlar" role="menuitem" onClick={() => setMenuOpen(false)}>
                  Hesap ayarları
                </Link>
                {user?.role === "admin" ? (
                  <Link href="/yonetim" role="menuitem" onClick={() => setMenuOpen(false)}>
                    Yönetim
                  </Link>
                ) : null}
                <button type="button" role="menuitem" className="account-menu-exit" onClick={() => void logout()}>
                  Çıkış
                </button>
              </div>
            ) : null}
          </div>
        </div>
      </header>
      <div
        className={`workspace${showInspector ? "" : " no-inspector"}`}
        style={
          {
            "--nav-width": `${navWidth}px`,
            ...(showInspector ? { "--inspector-width": `${inspectorWidth}px` } : {}),
          } as CSSProperties
        }
      >
        <aside className="side-nav">
          {sidebarTitle ? <h2>{sidebarTitle}</h2> : null}
          <ul>
            {navSections.map((section, sectionIndex) => (
              <li key={section.title ?? sectionIndex} className={section.title ? "side-nav-group" : undefined}>
                {section.title ? <span className="side-nav-group-title">{section.title}</span> : null}
                <ul>
                  {section.items.map((item) => (
                    <li key={item.id}>
                      <button
                        type="button"
                        className={sidebarActive === item.id ? "active" : ""}
                        onClick={() => onSidebarSelect(item.id)}
                      >
                        {item.label}
                      </button>
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
          {quote ? (
            <div className="side-quote">
              <p>{quote}</p>
              {quoteMeta ? <span>{quoteMeta}</span> : null}
            </div>
          ) : null}
        </aside>
        <button
          type="button"
          className="pane-resizer"
          aria-label="Sol paneli boyutlandır"
          onPointerDown={(event) => onResizeStart("nav", event)}
          onPointerMove={onResizeMove}
          onPointerUp={onResizeEnd}
          onPointerCancel={onResizeEnd}
        />
        {children}
        {showInspector ? (
          <>
            <button
              type="button"
              className="pane-resizer"
              aria-label="Sağ paneli boyutlandır"
              onPointerDown={(event) => onResizeStart("inspector", event)}
              onPointerMove={onResizeMove}
              onPointerUp={onResizeEnd}
              onPointerCancel={onResizeEnd}
            />
            <aside className="inspector">
              <div className="inspector-head">
                <h2>{inspectorTitle}</h2>
                {onInspectorModeChange ? (
                  <button
                    type="button"
                    className="inspector-close"
                    onClick={() => onInspectorModeChange("collapsed")}
                  >
                    Kapat
                  </button>
                ) : null}
              </div>
              {inspector}
            </aside>
          </>
        ) : null}
      </div>
      {hideStatusBar ? null : (
        <footer className="status-bar">
          <span>{footer ?? ""}</span>
        </footer>
      )}
    </div>
  );
}
