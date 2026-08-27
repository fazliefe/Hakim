"use client";

import { FormEvent, useState } from "react";
import { DocumentAnalysis, StructuredDocument, VisualEk, analyzeEvrakFile, analyzeEvrakVision, analyzeWorkspace, visionFile } from "@/lib/api";

export const SAMPLE_EVRAK = `T.C.
ANKARA 4. AĞIR CEZA MAHKEMESİ
GEREKÇELİ KARAR

Sanığın 5237 sayılı TCK'nın 158/1-f maddesinde düzenlenen nitelikli dolandırıcılık suçundan mahkûmiyetine karar verildi. Hükmün istinaf kanun yolunun açık olduğuna.

Karar tarihi: 01.08.2026
Tebliğ tarihi: 14.08.2026`;

export function useDocumentAnalysis(
  path: "/v1/evrak" | "/v1/surec" | "/v1/islem" | "/v1/senaryo",
  initialAction?: string,
  initialText?: string,
) {
  // Metin kutusu BOŞ başlar (sabit örnek otomatik doldurulmuyor) — önceden
  // SAMPLE_EVRAK varsayılan olarak yükleniyordu, sabit bir tebliğ tarihi
  // (14.08.2026) içeriyordu ve kullanıcılar tarihi değiştirmeden tekrar
  // gönderince süre hesabı hep aynı (28.08.2026) çıkıyor, sanki motor
  // hardcoded'muş gibi bir izlenim veriyordu. `SAMPLE_EVRAK` "örnek yükle"
  // butonu için hâlâ export ediliyor.
  const [text, setText] = useState(initialText ?? "");
  const [action, setAction] = useState(initialAction ?? "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<DocumentAnalysis | null>(null);

  const [fileName, setFileName] = useState<string | null>(null);
  const [structured, setStructured] = useState<StructuredDocument | null>(null);

  async function submit(event?: FormEvent, nextAction?: string, nextText?: string, visualEks?: VisualEk[]) {
    event?.preventDefault();
    const usedAction = nextAction ?? action;
    const payload = (nextText ?? text).trim();
    if (nextAction) setAction(nextAction);
    if (nextText) setText(nextText);
    setLoading(true);
    setError(null);
    setStructured(null);
    try {
      const data = await analyzeWorkspace(
        path,
        payload,
        path === "/v1/islem" || path === "/v1/senaryo" ? usedAction || undefined : undefined,
        path === "/v1/islem" ? visualEks : undefined,
      );
      setResult(data);
      if (path === "/v1/islem" && usedAction && data.action) setAction(data.action);
      if (path === "/v1/senaryo" && data.action) setAction(data.action);
    } catch (err) {
      // Önceki (başarılı) sonucu ekranda bırakmak, kullanıcıya bu isteğin de
      // aynı sonucu ürettiği izlenimini veriyordu — hata mesajının yanında
      // eski süre/karar bilgisi görünmeye devam ediyordu.
      setResult(null);
      setError(err instanceof Error ? err.message : "Bilinmeyen hata");
    } finally {
      setLoading(false);
    }
  }

  async function submitFile(file: File, _opts?: { vision?: boolean }) {
    setLoading(true);
    setError(null);
    setStructured(null);
    try {
      if (visionFile(file)) {
        const vision = await analyzeEvrakVision(file);
        setFileName(vision.filename || file.name);
        if (vision.quality?.status === "unusable") {
          setStructured(null);
          setResult(null);
          setError("Görüntü kullanılamaz. Daha net, düz ve aydınlık bir fotoğraf çekin.");
          return null;
        }
        setStructured(vision);
        const fromText = (vision.raw_text || "").replace(/\[okunamadı\]/g, " ").replace(/[ \t]+\n/g, "\n").trim();
        const fromFields = (vision.fields || [])
          .filter((field) => field.value && field.value !== "[okunamadı]")
          .map((field) => `${field.label}: ${field.value}`)
          .join("\n");
        const textOut = fromText.length >= 8 ? fromText : fromFields;
        if (textOut.length < 8) {
          setResult(null);
          setError("Fotoğraftan yeterli metin okunamadı. Daha net çekin veya PDF yükleyin.");
          return null;
        }
        setText(textOut);
        const data = await analyzeWorkspace(
          path,
          textOut,
          path === "/v1/islem" || path === "/v1/senaryo" ? action || undefined : undefined,
        );
        data.source_filename = vision.filename || file.name;
        data.source_kind = "image";
        data.extract_note = "Evren görüntü";
        data.text = textOut;
        setResult(data);
        return data;
      }
      const data = await analyzeEvrakFile(file);
      setResult(data);
      setFileName(data.source_filename || file.name);
      if (data.text) setText(data.text);
      return data;
    } catch (err) {
      setResult(null);
      setStructured(null);
      setError(err instanceof Error ? err.message : "Dosya okunamadı");
      return null;
    } finally {
      setLoading(false);
    }
  }

  async function submitSenaryo(nextAction?: string, nextText?: string) {
    const usedAction = nextAction ?? action;
    const payload = (nextText ?? text).trim();
    if (nextAction) setAction(nextAction);
    if (nextText) setText(nextText);
    setLoading(true);
    setError(null);
    try {
      const data = await analyzeWorkspace("/v1/senaryo", payload, usedAction || undefined);
      setResult(data);
      if (data.action) setAction(data.action);
      return true;
    } catch (err) {
      setResult(null);
      setError(err instanceof Error ? err.message : "Senaryo çalışmadı");
      return false;
    } finally {
      setLoading(false);
    }
  }

  return { text, setText, action, setAction, loading, error, result, setResult, submit, submitFile, submitSenaryo, fileName, setFileName, structured };
}

export const TYPE_LABEL: Record<string, string> = {
  tebligat: "Tebligat",
  iddianame: "İddianame",
  mahkeme_karari: "Mahkeme Kararı",
  dilekce: "Dilekçe",
  ust_yazi: "Üst Yazı",
  olur: "Olur",
  genelge: "Genelge",
  tutanak: "Tutanak",
  rapor: "Rapor",
  cevap_yazisi: "Cevap Yazısı",
  bilgi_yazisi: "Bilgi Yazısı",
  belirsiz: "Tür Belirsiz",
};

export const FIELD_LABEL: Record<string, string> = {
  sayi: "Sayı",
  konu: "Konu",
  ilgi: "İlgi",
  kurum: "Kurum",
  muhatap: "Muhatap",
  tarih: "Tarih",
  teblig: "Tebliğ Tarihi",
  karar: "Karar Tarihi",
  ek: "Ek",
  dagitim: "Dağıtım",
};

export const NATURE_LABEL: Record<string, string> = {
  ceza: "Ceza",
  hukuk: "Hukuk",
  idare: "İdare",
  anayasa: "Anayasa",
  kamu: "Kamu İdaresi",
  belirsiz: "Belirsiz",
};

export const STAGE_LABEL: Record<string, string> = {
  sorusturma: "Soruşturma",
  kovusturma: "Kovuşturma",
  ilk_derece: "İlk Derece",
  istinaf: "İstinaf",
  temyiz: "Temyiz",
  bireysel_basvuru: "Bireysel Başvuru",
  belirsiz: "Belirsiz",
};

// backend: services/llm/answers.py::BELGE_TITLE — belge/action id'sini arayüzde
// ham (snake_case) göstermemek için.
export const BELGE_LABEL: Record<string, string> = {
  istinaf: "İstinaf dilekçesi",
  temyiz: "Temyiz dilekçesi",
  itiraz: "İtiraz dilekçesi",
  cevap: "Cevap dilekçesi",
  sikayet: "Şikayet dilekçesi",
  suc_duyurusu: "Suç duyurusu",
  katilma: "Davaya katılma talebi",
  bireysel_basvuru: "Bireysel başvuru dilekçesi",
  idari_dava: "İdari dava dilekçesi",
  tahliye: "Tahliye talebi",
  adli_kontrol_itiraz: "Adli kontrol / tutuklama itirazı",
  ust_yazi: "Üst yazı",
  bilgi_yazisi: "Bilgi yazısı",
  olur: "Olur yazısı",
  cevap_yazisi: "Cevap yazısı",
};
