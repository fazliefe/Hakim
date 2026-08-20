"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ChangeEvent, useEffect, useMemo, useState } from "react";
import { AgentRail } from "@/components/AgentRail";
import { AppShell } from "@/components/AppShell";
import { PetitionPreview } from "@/components/PetitionPreview";
import { ReasoningPanel } from "@/components/ReasoningPanel";
import { BelgeKalip, getBelgeler, getKamuSablon, KamuSablon, writerLabel } from "@/lib/api";
import { KAMU_FALLBACK, KAMU_SAMPLES, SABLON_BLOCK_LABELS } from "@/lib/kamuSamples";
import { FIELD_LABEL, useDocumentAnalysis } from "@/lib/useDocumentAnalysis";

function kamuSample(id: string, sablon: KamuSablon | null) {
  return sablon?.ornekler?.[id] || KAMU_SAMPLES[id] || KAMU_SAMPLES.ust_yazi;
}

export function KamuWorkbench() {
  const params = useSearchParams();
  const initialKalip = params.get("kalip") ?? "ust_yazi";
  const [kalipList, setKalipList] = useState<BelgeKalip[]>(KAMU_FALLBACK);
  const [sablon, setSablon] = useState<KamuSablon | null>(null);
  const [side, setSide] = useState(initialKalip === "sablon" ? "sablon" : initialKalip);

  const { text, setText, action, setAction, loading, error, result, submitSenaryo, submitFile, fileName } =
    useDocumentAnalysis(
      "/v1/senaryo",
      initialKalip !== "sablon" ? initialKalip : "ust_yazi",
      KAMU_SAMPLES[initialKalip !== "sablon" ? initialKalip : "ust_yazi"] ?? KAMU_SAMPLES.ust_yazi,
    );

  useEffect(() => {
    getBelgeler()
      .then((rows) => {
        const kamu = rows.filter((item) => item.family === "kamu");
        if (kamu.length) setKalipList(kamu);
      })
      .catch(() => setKalipList(KAMU_FALLBACK));
    getKamuSablon()
      .then((payload) => {
        setSablon(payload);
        const kalip = initialKalip !== "sablon" && initialKalip !== "kaynaklar" ? initialKalip : "ust_yazi";
        if (payload.ornekler?.[kalip]) setText(payload.ornekler[kalip]);
      })
      .catch(() => setSablon(null));
  }, [initialKalip, setText]);

  const selected = useMemo(
    () => kalipList.find((item) => item.id === side) ?? kalipList[0],
    [kalipList, side],
  );

  const variant = sablon?.varyantlar?.[side] ?? sablon?.varyantlar?.[selected?.id ?? "ust_yazi"];

  function onSide(id: string) {
    setSide(id);
    if (id === "sablon" || id === "kaynaklar") return;
    setAction(id);
    setText(kamuSample(id, sablon));
  }

  function onFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    void submitFile(file).then((data) => {
      if (data?.text) {
        const kalip = side === "sablon" || side === "kaynaklar" ? "ust_yazi" : side;
        void submitSenaryo(kalip, data.text);
      }
    });
  }

  const sidebarSections = [
    {
      title: "Yazışma kalıpları",
      items: kalipList.map((item) => ({ id: item.id, label: item.title })),
    },
    {
      title: "2646 Ek",
      items: [
        { id: "sablon", label: "Şablon düzeni" },
        { id: "kaynaklar", label: "Kaynaklar" },
      ],
    },
  ];

  return (
    <AppShell
      module="kamu"
      sidebarTitle="Kamu yazışmaları"
      sidebarSections={sidebarSections}
      sidebarActive={side}
      onSidebarSelect={onSide}
      quote="“Sayı, konu, muhatap — sıra bozulmaz.”"
      quoteMeta="2646 Yönetmelik Ek"
      inspectorTitle="Kalıp / dayanak"
      inspector={
        side === "kaynaklar" ? (
          <div className="kamu-inspector">
            <p className="muted">Yazışma kalıplarının dayandığı resmi siteler. HÂKİM gönderim yapmaz.</p>
            {(sablon?.kaynaklar ?? []).map((item) => (
              <a key={item.id || item.url} className="kamu-source-mini" href={item.url} target="_blank" rel="noreferrer">
                {item.name}
              </a>
            ))}
          </div>
        ) : side === "sablon" ? (
          <div className="kamu-inspector">
            <p className="muted">Resmî Yazışma Yönetmeliği Ek örneklerindeki blok sırası.</p>
            {variant?.blok_sirasi?.map((blockId, index) => (
              <div key={blockId} className="kamu-block-row">
                <span>{index + 1}</span>
                <strong>{SABLON_BLOCK_LABELS[blockId] ?? blockId}</strong>
              </div>
            )) ?? <p className="muted">Şablon yüklenemedi.</p>}
          </div>
        ) : selected ? (
          <div className="kamu-inspector">
            <p>{selected.when}</p>
            <p className="muted">Makam: {selected.makam}</p>
            {result?.fields && Object.keys(result.fields).length ? (
              <>
                <h3>Gelen evrak alanları</h3>
                <ul className="kamu-section-list">
                  {Object.entries(result.fields).map(([key, value]) => (
                    <li key={key}>
                      {FIELD_LABEL[key] ?? key}: {value}
                    </li>
                  ))}
                </ul>
              </>
            ) : null}
            {selected.sections.length ? (
              <>
                <h3>Bölümler</h3>
                <ul className="kamu-section-list">
                  {selected.sections.map((label) => (
                    <li key={label}>{label}</li>
                  ))}
                </ul>
              </>
            ) : null}
            {selected.legal_basis.length ? (
              <>
                <h3>Dayanak</h3>
                <ul className="kamu-section-list legal">
                  {selected.legal_basis.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </>
            ) : null}
          </div>
        ) : (
          <p className="muted">Soldan bir kalıp seçin.</p>
        )
      }
      footer={
        loading
          ? "Kamu yazışması üretiliyor…"
          : result?.draft
            ? `${selected?.title ?? side} · ${writerLabel(result.writer)}`
            : "2646 Ek düzenine uygun taslak"
      }
    >
      <section className="main-pane kamu-pane">
        <div className="pane-hero">
          <h1>
            {side === "sablon"
              ? "Şablon düzeni"
              : side === "kaynaklar"
                ? "Kamu kaynakları"
                : selected?.title ?? "Kamu yazışması"}
          </h1>
          <p>
            {side === "sablon"
              ? "Yönetmelik Ek’teki resmi blok sırası. Üretilen taslaklar bu düzene göre biçimlenir."
              : side === "kaynaklar"
                ? "Resmî yazışmanın birincil kaynakları. Bağlar resmi sitelere açılır."
                : "Gelen kamu evrakından (üst yazı, olur, genelge, cevap) Sayı/Konu/Muhatap alınır; taslak 2646 düzeninde yazılır."}{" "}
            <Link href="/evrak" className="kamu-inline-link">
              Evrak →
            </Link>
          </p>
        </div>

        {error ? <p className="error kamu-error">{error}</p> : null}
        <AgentRail
          agents={result?.agents}
          chainStatus={result?.chain_status}
          observability={result?.observability}
        />
        {result?.reasoning && side !== "sablon" && side !== "kaynaklar" ? (
          <ReasoningPanel reasoning={result.reasoning} />
        ) : null}

        {side === "kaynaklar" ? (
          <div className="kamu-source-list">
            {(sablon?.kaynaklar ?? []).map((item) => (
              <a key={item.id || item.url} className="kamu-source-card" href={item.url} target="_blank" rel="noreferrer">
                <span className="kamu-sablon-id">{item.kind ?? "kaynak"}</span>
                <strong>{item.name}</strong>
                {item.note ? <p>{item.note}</p> : null}
                <span className="kamu-source-url">{item.url}</span>
              </a>
            ))}
            {!sablon?.kaynaklar?.length ? (
              <p className="muted evrak-hint">Kaynak listesi yüklenemedi. API’nin açık olduğundan emin olun.</p>
            ) : null}
          </div>
        ) : side === "sablon" ? (
          <div className="kamu-sablon-grid">
            {Object.entries(sablon?.bloklar ?? {}).map(([id, block]) => (
              <article key={id} className="kamu-sablon-card">
                <span className="kamu-sablon-id">{block.ornek ?? id}</span>
                <strong>{SABLON_BLOCK_LABELS[id] ?? id}</strong>
                <p>{block.kurallar}</p>
              </article>
            ))}
          </div>
        ) : (
          <div className="kamu-desk">
            <form
              className="doc-sheet kamu-sheet"
              onSubmit={(event) => {
                event.preventDefault();
                void submitSenaryo(side);
              }}
            >
              <header className="sheet-head">
                <span>{fileName ? fileName : "Gelen kamu evrakı"}</span>
                <div className="sheet-actions">
                  <label className="file-btn">
                    Evrak yükle
                    <input
                      type="file"
                      accept=".pdf,.txt,.md,application/pdf,text/plain"
                      onChange={onFile}
                      disabled={loading}
                    />
                  </label>
                  <button type="submit" disabled={loading || text.trim().length < 8}>
                    {loading ? "Üretiliyor…" : "Taslak üret"}
                  </button>
                </div>
              </header>
              <textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                aria-label="Kamu evrak metni"
                spellCheck={false}
              />
            </form>
            <div className="kamu-aside">
              {variant ? (
                <div className="kamu-variant-card">
                  <span>2646 Ek</span>
                  <strong>{variant.ornek ?? variant.belge_id}</strong>
                  <p className="muted">Kapanış: {variant.kapanis ?? "rica ederim"}</p>
                </div>
              ) : null}
              {result?.draft ? (
                <PetitionPreview
                  petition={result.petition}
                  draft={result.draft}
                  badge={result.belge ?? action}
                />
              ) : (
                <p className="muted evrak-hint">
                  Kalıp örneği veya yüklenen evraktan Sayı, Konu, Muhatap ve İlgi alınır. Çıktı 2646 blok sırasını korur.
                </p>
              )}
            </div>
          </div>
        )}
      </section>
    </AppShell>
  );
}
