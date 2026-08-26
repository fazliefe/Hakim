import { Suspense } from "react";
import { SessionSplash } from "@/components/AuthGate";
import { EvrakWorkbench } from "@/components/EvrakWorkbench";

export default function EvrakPage() {
  return (
    <Suspense fallback={<SessionSplash message="Yükleniyor…" />}>
      <EvrakWorkbench />
    </Suspense>
  );
}
