"use client";

import Image from "next/image";
import Link from "next/link";
import { ReactNode, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { SystemStatus, getSystemStatus } from "@/lib/api";

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
  { href: "/kamu", id: "kamu", label: "Kamu", subtle: true },
  { href: "/surec", id: "surec", label: "Süreç" },
  { href: "/islem", id: "islem", label: "İşlem" },
] as const;

export type HakimModule = (typeof MODULES)[number]["id"];

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
  footer,
  children,
}: {
  module: HakimModule;
  sidebarTitle: string;
  sidebarItems?: SidebarItem[];
  sidebarSections?: SidebarSection[];
  sidebarActive: string;
  onSidebarSelect: (id: string) => void;
  quote: string;
  quoteMeta: string;
  inspectorTitle: string;
  inspector: ReactNode;
  footer: string;
  children: ReactNode;
}) {
  const router = useRouter();
  const [status, setStatus] = useState<SystemStatus | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = () => {
      getSystemStatus()
        .then((data) => {
          if (!cancelled) setStatus(data);
        })
        .catch(() => {
          if (!cancelled) {
            setStatus({
              status: "kapalı",
              service: "hakim-api",
              ready: false,
              checks: { api: "kapalı", elasticsearch: "kapalı", neo4j: "kapalı", postgres: "kapalı", yazim: "kapalı" },
            });
          }
        });
    };
    load();
    const timer = window.setInterval(load, 15000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  function logout() {
    window.sessionStorage.removeItem("hakim-auth");
    window.sessionStorage.removeItem("hakim-scale-bias");
    router.push("/giris");
  }

  const navSections =
    sidebarSections ??
    (sidebarItems ? [{ items: sidebarItems }] : []);

  return (
    <div className="app-shell" data-module={module}>
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
              className={[module === item.id ? "active" : "", "subtle" in item && item.subtle ? "subtle" : ""]
                .filter(Boolean)
                .join(" ")}
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="topbar-actions">
          <div className="system-pills compact" aria-label="Sistem durumu">
            {CHECK_LABELS.map(([key, label]) => {
              const ok = status?.checks[key] === "ok";
              return (
                <span key={key} className={`sys-pill ${ok ? "ok" : "down"}`}>
                  <i />
                  {label}
                </span>
              );
            })}
          </div>
          <button type="button" className="btn-ghost topbar-exit" onClick={logout}>
            Çıkış
          </button>
        </div>
      </header>
      <div className="workspace">
        <aside className="side-nav">
          <h2>{sidebarTitle}</h2>
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
          <div className="side-quote">
            <p>{quote}</p>
            <span>{quoteMeta}</span>
          </div>
        </aside>
        {children}
        <aside className="inspector">
          <h2>{inspectorTitle}</h2>
          {inspector}
        </aside>
      </div>
      <footer className="status-bar">
        <span>{footer}</span>
        <span>HÂKİM · Kodun dili, geleceğin Hakimi.</span>
      </footer>
    </div>
  );
}
