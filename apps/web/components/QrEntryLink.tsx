"use client";

import Link from "next/link";

function QrMark() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="currentColor"
        d="M3 3h8v8H3zm2 2v4h4V5zm8-2h8v8h-8zm2 2v4h4V5zM3 13h8v8H3zm2 2v4h4v-4zm10-2h2v2h-2zm4 0h2v2h-2zm-2 2h2v2h-2zm2 2h2v2h-2zm-4 0h2v2h-2zm-2 2h2v2h-2zm4 0h2v2h-2zm2 2h2v2h-2z"
      />
    </svg>
  );
}

export function QrEntryLink({ variant = "chip" }: { variant?: "chip" | "login" }) {
  if (variant === "login") {
    return (
      <Link href="/qr" className="login-qr" aria-label="Mobil QR kodunu aç">
        <QrMark />
        Telefonda aç
      </Link>
    );
  }
  return (
    <Link href="/qr" className="qr-entry" aria-label="Mobil QR kodunu aç">
      <QrMark />
    </Link>
  );
}
