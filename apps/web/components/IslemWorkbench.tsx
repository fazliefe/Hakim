"use client";

import { ChangeEvent, FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { PetitionPreview } from "@/components/PetitionPreview";
import { BelgeKalip, IslemGuess, getBelgeler, guessIslem, screenIslemPhoto, visionFile } from "@/lib/api";
import { DownloadActions } from "@/components/DownloadActions";
import { petitionToBlocks } from "@/lib/exportDocument";
import { useDocumentAnalysis } from "@/lib/useDocumentAnalysis";
import { titleCaseLabel } from "@/lib/labels";

const FALLBACK: BelgeKalip[] = [
  { id: "sikayet", title: "Şikayet Dilekçesi", when: "Savcılığa Şikayet", makam: "Cumhuriyet Başsavcılığı", legal_basis: [], sections: [] },
  { id: "suc_duyurusu", title: "Suç Duyurusu", when: "İhbar", makam: "Cumhuriyet Başsavcılığı", legal_basis: [], sections: [] },
  { id: "cevap", title: "Cevap Dilekçesi", when: "İddiaya Cevap", makam: "Görevli Ceza Mahkemesi", legal_basis: [], sections: [] },
  { id: "itiraz", title: "İtiraz Dilekçesi", when: "CMK m.268", makam: "İtiraz Mercii", legal_basis: [], sections: [] },
  { id: "istinaf", title: "İstinaf Dilekçesi", when: "CMK m.273", makam: "Bölge Adliye Mahkemesi", legal_basis: [], sections: [] },
  { id: "temyiz", title: "Temyiz Dilekçesi", when: "CMK m.291", makam: "Yargıtay", legal_basis: [], sections: [] },
  { id: "temyiz_cevap", title: "Temyize Cevap", when: "Hukuk Temyiz Cevabı", makam: "Yargıtay Başkanlığı", legal_basis: [], sections: [] },
  { id: "katilma", title: "Davaya Katılma", when: "CMK m.237", makam: "Ceza Mahkemesi", legal_basis: [], sections: [] },
  { id: "bireysel_basvuru", title: "Bireysel Başvuru", when: "AYM", makam: "Anayasa Mahkemesi", legal_basis: [], sections: [] },
  { id: "idari_dava", title: "İdari Dava Dilekçesi", when: "İYUK", makam: "İdare Mahkemesi", legal_basis: [], sections: [] },
  { id: "tahliye", title: "Tahliye Talebi", when: "Tutukluluk", makam: "Mahkeme / Hakimlik", legal_basis: [], sections: [] },
  { id: "ihtiyac_tahliye", title: "İhtiyaç Tahliyesi", when: "Kira / Sulh Hukuk", makam: "Sulh Hukuk Mahkemesi", legal_basis: [], sections: [] },
  { id: "sure_uzatim", title: "Süre Uzatım Talebi", when: "Hukuk Cevap Süresi", makam: "Hukuk Mahkemesi", legal_basis: [], sections: [] },
  { id: "icra_borca_itiraz", title: "Borca İtiraz", when: "İlamsız İcra / Ödeme Emri", makam: "İcra Müdürlüğü", legal_basis: [], sections: [] },
  { id: "adli_kontrol_itiraz", title: "Adli Kontrol İtirazı", when: "Koruma Tedbiri", makam: "İtiraz Mercii", legal_basis: [], sections: [] },
];

const SIDE = [{ id: "yazim", label: "Yazım" }];

function gapPlaceholder(id: string): string {
  switch (id) {
    case "olay_tarihi":
    case "teblig":
      return "gg.aa.yyyy";
    case "sikayetci":
    case "ad_soyad":
      return "Ad Soyad";
    case "adres":
      return "Mahalle, sokak, no";
    case "il":
      return "Ankara";
    case "sikayet_edilen":
      return "Ad Soyad veya kimliği belirsiz";
    case "olay_yeri":
      return "İl / ilçe / şube";
    case "delil":
      return "Dekont, mesaj, tanık…";
    case "mahkeme":
      return "Mahkeme adı";
    case "esas":
      return "2025/412";
    case "anlatim":
      return "Olayı kısaca yazın";
    default:
      return "Bildiklerinizi yazın";
  }
}

function gapLine(id: string, value: string): string {
  const v = value.trim();
  if (!v) return "";
  switch (id) {
    case "sikayetci":
      return `Şikayetçi: ${v}`;
    case "ad_soyad":
      return `Ad soyad: ${v}`;
    case "adres":
      return `Adres: ${v}`;
    case "il":
      return `İl: ${v}`;
    case "sikayet_edilen":
      return `Şikayet edilen: ${v}`;
    case "olay_tarihi":
      return `Olay tarihi: ${v}`;
    case "olay_yeri":
      return `Olay yeri: ${v}`;
    case "delil":
      return `Deliller: ${v}`;
    case "teblig":
      return `Tebliğ tarihi: ${v}`;
    case "mahkeme":
      return `Mahkeme: ${v}`;
    case "esas":
      return `Esas No: ${v}`;
    case "anlatim":
      return v;
    default:
      return `${id}: ${v}`;
  }
}

const AUTO_EXAMPLES: Array<{ label: string; expect: string; text: string }> = [
  {
    label: "Şikayet",
    expect: "sikayet",
    text: "Banka hesabımdan paramı aldılar, dolandırıldım. Savcılığa şikayet etmek istiyorum.",
  },
  {
    label: "Suç duyurusu",
    expect: "suc_duyurusu",
    text: "Komşunun evinde silah gördüm. Suç duyurusunda bulunmak istiyorum.",
  },
  {
    label: "Cevap",
    expect: "cevap",
    text: "İddianame tebliğ edildi. Cevap dilekçesi vermek istiyorum.",
  },
  {
    label: "İtiraz",
    expect: "itiraz",
    text: "Sulh ceza hakimliği tutuklama kararına itiraz dilekçesi yazmak istiyorum.",
  },
  {
    label: "İstinaf",
    expect: "istinaf",
    text: "Ağır ceza mahkemesinin mahkumiyet hükmünü istinaf etmek istiyorum, bölge adliye mahkemesine.",
  },
  {
    label: "Temyiz",
    expect: "temyiz",
    text: "BAM kararı tebliğ edildi. Yargıtay’a temyiz etmek istiyorum.",
  },
  {
    label: "Temyize cevap",
    expect: "temyiz_cevap",
    text: "Karşı tarafın temyizine cevap dilekçesi yazmak istiyorum.",
  },
  {
    label: "Katılma",
    expect: "katilma",
    text: "Açılan ceza davasında katılan sıfatıyla davaya katılma talebinde bulunmak istiyorum.",
  },
  {
    label: "AYM",
    expect: "bireysel_basvuru",
    text: "İç hukuk yolları tükendi. Anayasa Mahkemesine bireysel başvuru yapmak istiyorum.",
  },
  {
    label: "İdari dava",
    expect: "idari_dava",
    text: "Valiliğin idari işlemine karşı iptal davası açmak istiyorum, idare mahkemesine.",
  },
  {
    label: "Tahliye",
    expect: "tahliye",
    text: "Tutukluyum. Tahliye talebinde bulunmak istiyorum.",
  },
  {
    label: "İhtiyaç tahliyesi",
    expect: "ihtiyac_tahliye",
    text: "Kiracıyı ihtiyaç sebebiyle tahliye etmek istiyorum, sulh hukuk mahkemesine.",
  },
  {
    label: "Süre uzatımı",
    expect: "sure_uzatim",
    text: "Hukuk mahkemesinde cevap süresi uzatım talebi dilekçesi yazmak istiyorum.",
  },
  {
    label: "Borca itiraz",
    expect: "icra_borca_itiraz",
    text: "İlamsız icra takibine borca itiraz dilekçesi vermek istiyorum, icra müdürlüğüne.",
  },
  {
    label: "Adli kontrol",
    expect: "adli_kontrol_itiraz",
    text: "Adli kontrol kapsamında imza yükümlülüğü ve yurt dışı yasağı var, buna itiraz etmek istiyorum.",
  },
];

const PHOTO_ACCEPT = "image/jpeg,image/png,image/webp,image/tiff,.jpg,.jpeg,.png,.webp,.tif,.tiff";
const MAX_CHAT_PHOTOS = 4;

type ChatPhoto = {
  id: string;
  name: string;
  src: string;
  caption: string;
  scene: string;
};

export function IslemWorkbench() {
  const { text, setText, action, setAction, loading, error, result, submit } = useDocumentAnalysis("/v1/islem");
  const [side, setSide] = useState("yazim");
  const [mode, setMode] = useState<"auto" | "manual">("auto");
  const [kalip, setKalip] = useState<BelgeKalip[]>(FALLBACK);
  const [guess, setGuess] = useState<IslemGuess | null>(null);
  const [gapAnswers, setGapAnswers] = useState<Record<string, string>>({});
  const [photos, setPhotos] = useState<ChatPhoto[]>([]);
  const [photoBusy, setPhotoBusy] = useState(false);
  const [photoError, setPhotoError] = useState<string | null>(null);
  const photosRef = useRef<ChatPhoto[]>([]);
  photosRef.current = photos;

  useEffect(() => {
    return () => {
      photosRef.current.forEach((photo) => URL.revokeObjectURL(photo.src));
    };
  }, []);

  useEffect(() => {
    getBelgeler()
      .then((rows) => {
        const dilekce = rows.filter((item) => item.family !== "kamu");
        const titled = (rows: BelgeKalip[]) =>
          rows.map((item) => ({ ...item, title: titleCaseLabel(item.title) }));
        if (dilekce.length) setKalip(titled(dilekce));
        else if (rows.length) setKalip(titled(rows));
      })
      .catch(() => setKalip(FALLBACK));
  }, []);

  useEffect(() => {
    if (mode !== "auto") return;
    const blob = text.trim();
    if (blob.length < 12) {
      setGuess(null);
      return;
    }
    const timer = window.setTimeout(() => {
      guessIslem(blob)
        .then(setGuess)
        .catch(() => setGuess(null));
    }, 420);
    return () => window.clearTimeout(timer);
  }, [text, mode]);

  useEffect(() => {
    const ids = new Set((result?.gaps || []).map((gap) => gap.id));
    setGapAnswers((prev) => {
      const next: Record<string, string> = {};
      for (const [key, value] of Object.entries(prev)) {
        if (ids.has(key)) next[key] = value;
      }
      return next;
    });
  }, [result]);

  const hasGapAnswers = Object.values(gapAnswers).some((value) => value.trim());

  function applyGaps(event: FormEvent) {
    event.preventDefault();
    if (!result?.gaps?.length || !hasGapAnswers) return;
    const extra = result.gaps
      .map((gap) => gapLine(gap.id, gapAnswers[gap.id] || ""))
      .filter(Boolean)
      .join("\n");
    if (!extra) return;
    const next = [text.trim(), extra].filter(Boolean).join("\n");
    void submit(undefined, (mode === "manual" ? action : result.action) || "", next, visualEks());
  }

  function visualEks() {
    return photos.map((photo) => ({ caption: photo.caption, scene: photo.scene }));
  }

  function dropPhoto(id: string) {
    setPhotos((prev) => {
      const gone = prev.find((item) => item.id === id);
      if (gone) URL.revokeObjectURL(gone.src);
      return prev.filter((item) => item.id !== id);
    });
  }

  async function onPhotos(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files || []);
    event.target.value = "";
    if (!files.length) return;
    const room = MAX_CHAT_PHOTOS - photos.length;
    if (room <= 0) {
      setPhotoError(`En fazla ${MAX_CHAT_PHOTOS} fotoğraf eklenebilir.`);
      return;
    }
    setPhotoBusy(true);
    setPhotoError(null);
    const accepted: ChatPhoto[] = [];
    try {
      for (const file of files.slice(0, room)) {
        if (!visionFile(file)) {
          setPhotoError("Yalnızca JPG, PNG veya WebP fotoğraf yükleyin.");
          continue;
        }
        try {
          const screened = await screenIslemPhoto(file);
          accepted.push({
            id: `${file.name}-${file.size}-${file.lastModified}-${Math.random().toString(36).slice(2, 8)}`,
            name: file.name,
            src: URL.createObjectURL(file),
            caption: screened.caption,
            scene: screened.scene,
          });
        } catch (err) {
          setPhotoError(err instanceof Error ? err.message : "Fotoğraf KVKK kontrolünden geçmedi.");
        }
      }
      if (accepted.length) setPhotos((prev) => [...prev, ...accepted].slice(0, MAX_CHAT_PHOTOS));
    } finally {
      setPhotoBusy(false);
    }
  }

  const detectedId = mode === "auto" ? result?.action || guess?.action : action;
  const selected = useMemo(
    () => kalip.find((item) => item.id === detectedId),
    [kalip, detectedId],
  );
  const verdictTitle = selected?.title ?? guess?.title ?? (mode === "manual" ? "Dilekçe" : "Anlatıdan dilekçe");
  const petitionReady = Boolean(
    result?.petition &&
      result.petition.layout !== "resmi" &&
      (result.petition.hitap || result.petition.sections?.length || result.petition.konu),
  );
  const petitionBlocks = petitionReady && result?.petition ? petitionToBlocks(result.petition) : undefined;
  const downloadBody = result?.draft || "";
  const downloadName = `hakim-dilekce-${detectedId || "taslak"}`;
  const downloads = (
    <DownloadActions
      content={downloadBody}
      blocks={petitionBlocks}
      basename={downloadName}
      disabled={!petitionBlocks?.length && !downloadBody}
    />
  );

  return (
    <AppShell
      module="islem"
      sidebarTitle="Dilekçe"
      sidebarItems={SIDE}
      sidebarActive={side}
      onSidebarSelect={setSide}
      inspectorTitle="Kontrol"
      inspector={
        result ? (
          <div className="islem-check">
            <ul className="check-list">
              <li className={result.belge ? "ok" : ""}>
                Kalıp: {verdictTitle}
              </li>
              <li className="ok">{mode === "auto" ? "Otomatik anlama" : "Manuel kalıp"}</li>
              {result.route_reason ? <li className="ok">{result.route_reason}</li> : null}
              {result.gaps?.length ? (
                <li className="gap-item">
                  Eksik ({result.gaps.length}) — soldaki kutuya yazın
                  <ul className="gap-mini">
                    {result.gaps.map((gap) => (
                      <li key={gap.id}>
                        {gap.label}: {gap.hint}
                      </li>
                    ))}
                  </ul>
                </li>
              ) : (
                <li className="ok">Anlatım yeterli</li>
              )}
              <li className={result.related.length ? "ok" : ""}>Kaynak doğrulandı ({result.related.length})</li>
              <li className={result.draft ? "ok" : ""}>Taslak hazır</li>
            </ul>
            <p className="muted">{result.uyap_note}</p>
            <div className="official-links">
              {result.official_targets.map((target) => (
                <a key={target.url} href={target.url} target="_blank" rel="noreferrer">
                  {target.name}
                </a>
              ))}
            </div>
          </div>
        ) : (
          <p className="muted">
            {mode === "auto"
              ? "Derdinizi yazın; sistem türü anlar ve o kalıpta yazar. UYAP gönderimi yok."
              : "Kalıbı siz seçin; anlatı o formata dökülür. UYAP gönderimi yok."}
          </p>
        )
      }
      footer={
        loading
          ? "Taslak Yazılıyor…"
          : result
            ? verdictTitle
            : "Dilekçe Bekleniyor"
      }
    >
      <section className="main-pane islem-pane">
        <div className="pane-hero">
          <h1>{result ? verdictTitle : "Dilekçe"}</h1>
          <p>
            {mode === "auto"
              ? "Derdinizi anlatın. Şikayet, istinaf, tahliye gibi türü sistem seçer ve o formatta yazar."
              : selected
                ? `${selected.when} · ${selected.makam}${selected.legal_basis?.length ? ` · ${selected.legal_basis.join(" · ")}` : ""}`
                : "Listeden kalıbı seçin, olayı yazın."}
          </p>
        </div>
        <form
          className="islem-compose"
          onSubmit={(event) => {
            setGapAnswers({});
            void submit(event, mode === "manual" ? action : "", undefined, visualEks());
          }}
        >
          <div className="mode-switch" role="tablist" aria-label="Yazım Modu">
            <button
              type="button"
              role="tab"
              aria-selected={mode === "auto"}
              className={mode === "auto" ? "on" : ""}
              onClick={() => {
                setMode("auto");
                setAction("");
              }}
            >
              Otomatik Anlama
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={mode === "manual"}
              className={mode === "manual" ? "on" : ""}
              onClick={() => setMode("manual")}
            >
              Manuel Kalıp
            </button>
          </div>
          {mode === "auto" ? (
            <div className="islem-examples" aria-label="Örnek Anlatılar">
              {AUTO_EXAMPLES.map((item) => (
                <button
                  key={item.expect}
                  type="button"
                  className={text === item.text ? "on" : ""}
                  onClick={() => setText(item.text)}
                >
                  {item.label}
                </button>
              ))}
            </div>
          ) : null}
          {mode === "manual" ? (
            <select
              className="kalip-select"
              aria-label="Dilekçe Kalıbı"
              value={action}
              onChange={(event) => setAction(event.target.value)}
            >
              <option value="">Kalıp Seçin</option>
              {kalip.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.title}
                </option>
              ))}
            </select>
          ) : guess ? (
            <p className="islem-guess" aria-live="polite">
              Bu bir <strong>{guess.title}</strong>.
              {guess.reason ? ` ${guess.reason}` : ""}
            </p>
          ) : (
            <p className="islem-guess muted">Anlatıyı yazın; tür burada görünecek.</p>
          )}
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            aria-label="Olay veya Dayanak Evrak"
            rows={6}
            spellCheck={false}
            placeholder={
              mode === "auto"
                ? "Örn. Bankada hesabımdan para çekildi, savcılığa şikayet etmek istiyorum."
                : "Olayı, tarihi ve tarafları yazın."
            }
          />
          <div className="islem-photos">
            <label className="file-btn">
              {photoBusy ? "KVKK kontrolü…" : "Fotoğraf ekle"}
              <input
                type="file"
                accept={PHOTO_ACCEPT}
                multiple
                onChange={onPhotos}
                disabled={loading || photoBusy || photos.length >= MAX_CHAT_PHOTOS}
                aria-label="Dilekçe eki fotoğrafı"
              />
            </label>
            <p className="muted islem-photos-hint">
              Fotoğraf KVKK kontrolünden geçerse EKLER’e alınır. Yüz, kimlik veya T.C. no içeren görüntü işlenmez.
            </p>
            {photos.length ? (
              <ul className="islem-photo-list">
                {photos.map((photo) => (
                  <li key={photo.id} className="islem-photo-chip">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={photo.src} alt={photo.caption} />
                    <span>{photo.caption}</span>
                    <button type="button" onClick={() => dropPhoto(photo.id)} aria-label={`${photo.caption} kaldır`}>
                      Kaldır
                    </button>
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
          <div className="islem-compose-actions">
            <button
              type="submit"
              disabled={loading || photoBusy || text.trim().length < 8 || (mode === "manual" && !action)}
            >
              {loading
                ? "Yazılıyor…"
                : mode === "manual" && selected
                  ? `${selected.title} Üret`
                  : guess
                    ? `${guess.title} Olarak Yaz`
                    : "Anla ve Uygun Dilekçeyi Yaz"}
            </button>
            {downloads}
          </div>
        </form>
        {error ? <p className="error">{error}</p> : null}
        {photoError ? <p className="error">{photoError}</p> : null}
        {result?.route_reason ? (
          <p className="evrak-verdict">
            {mode === "auto" ? `Bu bir ${verdictTitle.toLowerCase()}. ` : ""}
            {result.route_reason}
          </p>
        ) : null}
        {result?.gaps?.length ? (
          <aside className="gap-banner">
            <h2>Eksik Hususlar</h2>
            <p>Dilekçe yer tutucularla yazıldı. Aşağıya bildiklerinizi yazıp taslağı yenileyin; kimlik ve tarih uydurulmaz.</p>
            <form className="gap-form" onSubmit={applyGaps}>
              {result.gaps.map((gap) => (
                <label key={gap.id} className="gap-field">
                  <span>
                    <strong>{gap.label}</strong>
                    {gap.hint}
                  </span>
                  <input
                    value={gapAnswers[gap.id] || ""}
                    onChange={(event) =>
                      setGapAnswers((prev) => ({ ...prev, [gap.id]: event.target.value }))
                    }
                    placeholder={gapPlaceholder(gap.id)}
                    autoComplete="off"
                  />
                </label>
              ))}
              <button type="submit" disabled={loading || !hasGapAnswers}>
                {loading ? "Yenileniyor…" : "Eksikleri işle ve dilekçeyi yenile"}
              </button>
            </form>
          </aside>
        ) : null}
        {result ? (
          <PetitionPreview
            petition={result.petition}
            draft={result.draft}
            badge={verdictTitle}
            actions={downloads}
            ekImages={photos.map((photo) => ({ caption: photo.caption, src: photo.src }))}
          />
        ) : (
          <p className="muted islem-empty">
            {mode === "auto"
              ? "Derdinizi yazın; örneğin şikayet dilekçesi olduğunu anlayıp o kalıpta üretir."
              : "Kalıbı seçip olayı yazın."}
          </p>
        )}
      </section>
    </AppShell>
  );
}
