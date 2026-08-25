"use client";

import Image from "next/image";
import { ReactNode, useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { getAuthToken, getCurrentUser, getStoredUser } from "@/lib/api";

const PUBLIC_PATHS = new Set(["/", "/giris"]);

export function SessionSplash({ message = "Oturum Kontrol Ediliyor…" }: { message?: string }) {
  return (
    <div className="session-check">
      <div className="session-check-card">
        <Image src="/hakim-emblem.png" alt="" width={56} height={56} />
        <strong>HÂKİM</strong>
        <p>{message}</p>
      </div>
    </div>
  );
}

export function AuthGate({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [ready, setReady] = useState(PUBLIC_PATHS.has(pathname));

  useEffect(() => {
    if (PUBLIC_PATHS.has(pathname)) {
      setReady(true);
      return;
    }
    const token = getAuthToken();
    if (!token) {
      router.replace("/giris");
      return;
    }
    const cached = getStoredUser();
    if (cached) setReady(true);
    getCurrentUser()
      .then(() => setReady(true))
      .catch(() => {
        router.replace("/giris");
      });
  }, [pathname, router]);

  if (!ready) {
    return <SessionSplash />;
  }
  return children;
}
