import { Suspense } from "react";
import { SessionSplash } from "@/components/AuthGate";
import { AdminConsole } from "@/components/AdminConsole";

export default function YonetimPage() {
  return (
    <Suspense fallback={<SessionSplash message="Yükleniyor…" />}>
      <AdminConsole />
    </Suspense>
  );
}
