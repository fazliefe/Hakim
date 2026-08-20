"use client";

import { FormEvent, useState } from "react";
import { DocumentAnalysis, analyzeEvrakFile, analyzeWorkspace } from "@/lib/api";

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
  const [text, setText] = useState(initialText ?? (path === "/v1/islem" ? "" : SAMPLE_EVRAK));
  const [action, setAction] = useState(initialAction ?? "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<DocumentAnalysis | null>(null);

  const [fileName, setFileName] = useState<string | null>(null);

  async function submit(event?: FormEvent, nextAction?: string) {
    event?.preventDefault();
    const usedAction = nextAction ?? action;
    if (nextAction) setAction(nextAction);
    setLoading(true);
    setError(null);
    try {
      const data = await analyzeWorkspace(
        path,
        text.trim(),
        path === "/v1/islem" || path === "/v1/senaryo" ? usedAction || undefined : undefined,
      );
      setResult(data);
      if ((path === "/v1/islem" || path === "/v1/senaryo") && data.action) setAction(data.action);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Bilinmeyen hata");
    } finally {
      setLoading(false);
    }
  }

  async function submitFile(file: File) {
    setLoading(true);
    setError(null);
    try {
      const data = await analyzeEvrakFile(file);
      setResult(data);
      setFileName(data.source_filename || file.name);
      if (data.text) setText(data.text);
      return data;
    } catch (err) {
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
      setError(err instanceof Error ? err.message : "Senaryo çalışmadı");
      return false;
    } finally {
      setLoading(false);
    }
  }

  return { text, setText, action, setAction, loading, error, result, setResult, submit, submitFile, submitSenaryo, fileName };
}

export const TYPE_LABEL: Record<string, string> = {
  tebligat: "Tebligat",
  iddianame: "İddianame",
  mahkeme_karari: "Mahkeme kararı",
  dilekce: "Dilekçe",
  ust_yazi: "Üst yazı",
  olur: "Olur",
  genelge: "Genelge",
  tutanak: "Tutanak",
  rapor: "Rapor",
  cevap_yazisi: "Cevap yazısı",
  bilgi_yazisi: "Bilgi yazısı",
  belirsiz: "Tür belirsiz",
};

export const FIELD_LABEL: Record<string, string> = {
  sayi: "Sayı",
  konu: "Konu",
  ilgi: "İlgi",
  kurum: "Kurum",
  muhatap: "Muhatap",
  tarih: "Tarih",
  teblig: "Tebliğ tarihi",
  karar: "Karar tarihi",
  ek: "Ek",
  dagitim: "Dağıtım",
};

export const NATURE_LABEL: Record<string, string> = {
  ceza: "Ceza",
  idare: "İdare",
  anayasa: "Anayasa",
  kamu: "Kamu idaresi",
  belirsiz: "Belirsiz",
};

export const STAGE_LABEL: Record<string, string> = {
  sorusturma: "Soruşturma",
  kovusturma: "Kovuşturma",
  istinaf: "İstinaf",
  temyiz: "Temyiz",
  bireysel_basvuru: "Bireysel başvuru",
  belirsiz: "Belirsiz",
};
