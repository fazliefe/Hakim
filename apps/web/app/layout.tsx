import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "HÂKİM",
  description: "Kodun dili, geleceğin Hakimi. — Kaynak odaklı hukuki araştırma",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="tr">
      <body>{children}</body>
    </html>
  );
}
