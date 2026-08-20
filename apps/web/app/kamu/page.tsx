import { Suspense } from "react";
import { KamuWorkbench } from "@/components/KamuWorkbench";

export default function KamuPage() {
  return (
    <Suspense fallback={<p className="muted" style={{ padding: "2rem" }}>Yükleniyor…</p>}>
      <KamuWorkbench />
    </Suspense>
  );
}
