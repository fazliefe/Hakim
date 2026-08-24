const MONTHS = [
  "Ocak",
  "Şubat",
  "Mart",
  "Nisan",
  "Mayıs",
  "Haziran",
  "Temmuz",
  "Ağustos",
  "Eylül",
  "Ekim",
  "Kasım",
  "Aralık",
];

export function formatTurkishDate(iso?: string | null): string {
  if (!iso) return "—";
  const match = iso.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!match) return iso;
  const day = Number(match[3]);
  const month = Number(match[2]);
  if (month < 1 || month > 12) return iso;
  return `${day} ${MONTHS[month - 1]} ${match[1]}`;
}

export function durationUnitLabel(unit?: string | null): string {
  const key = (unit || "").toLowerCase();
  if (key === "day" || key === "days" || key === "gün") return "gün";
  if (key === "week" || key === "weeks" || key === "hafta") return "hafta";
  if (key === "month" || key === "months" || key === "ay") return "ay";
  if (key === "year" || key === "years" || key === "yıl") return "yıl";
  return unit || "";
}

export function calendarLabel(calendar?: string | null): string {
  if (calendar === "business") return "iş günü";
  if (calendar === "calendar") return "takvim günü";
  return calendar || "";
}

const HOP_TITLES: Record<string, string> = {
  sorgu: "Soru",
  query: "Soru",
  kontrol: "Kontrol",
  bm25: "Metin taraması",
  vektor: "Yakın hüküm",
  vector: "Yakın hüküm",
  rrf: "Birleşim",
  rerank: "Sıralama",
  graf: "Bağlantılar",
  graph: "Bağlantılar",
  cevap: "Cevap",
  answer: "Cevap",
  reddet: "Red",
};

export function hopTitle(id?: string, fallback?: string): string {
  const key = (id || "").toLowerCase();
  if (HOP_TITLES[key]) return HOP_TITLES[key];
  const fb = (fallback || "").trim().toLowerCase();
  if (HOP_TITLES[fb]) return HOP_TITLES[fb];
  if (/bm25/.test(fb)) return HOP_TITLES.bm25;
  if (/vekt|semantic/.test(fb)) return HOP_TITLES.vektor;
  if (/rrf|birleşim|birlesim/.test(fb)) return HOP_TITLES.rrf;
  if (/rerank/.test(fb)) return HOP_TITLES.rerank;
  if (/langgraph|langfuse|groq|openai|gpt-/.test(fb)) return "";
  return fallback || "";
}

export function hopStateLabel(state?: string | null): string {
  if (state === "done") return "tamam";
  if (state === "warn") return "üst adıma bağlı";
  if (state === "skip") return "bu türde yok";
  if (state === "error") return "hata";
  if (state === "think") return "işleniyor";
  if (state === "wait") return "sırada";
  return state || "";
}
