import { Suspense } from "react";
import { EvrakWorkbench } from "@/components/EvrakWorkbench";

export default function EvrakPage() {
  return (
    <Suspense fallback={<p className="muted" style={{ padding: "2rem" }}>Yükleniyor…</p>}>
      <EvrakWorkbench />
    </Suspense>
  );
}
