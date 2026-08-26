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
  if (calendar === "business") return "İş Günü";
  if (calendar === "calendar") return "Takvim Günü";
  return calendar || "";
}

const TITLE_SMALL = new Set(["ve", "ile", "veya", "ya"]);

export function titleCaseLabel(text: string): string {
  let seen = false;
  return text.replace(/[A-Za-zÇĞİÖŞÜçğıöşüÂÎÛâîû0-9’']+/g, (word) => {
    const lower = word.toLocaleLowerCase("tr-TR");
    const isFirst = !seen;
    seen = true;
    if (!isFirst && TITLE_SMALL.has(lower)) return lower;
    return lower.charAt(0).toLocaleUpperCase("tr-TR") + lower.slice(1);
  });
}

const HOP_TITLES: Record<string, string> = {
  sorgu: "Soru",
  query: "Soru",
  kontrol: "Kontrol",
  bm25: "Metin Taraması",
  vektor: "Yakın Hüküm",
  vector: "Yakın Hüküm",
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
  return fallback ? titleCaseLabel(fallback) : "";
}

export function hopStateLabel(state?: string | null): string {
  if (state === "done") return "Tamam";
  if (state === "warn") return "Üst Adıma Bağlı";
  if (state === "skip") return "Bu Türde Yok";
  if (state === "error") return "Hata";
  if (state === "think") return "İşleniyor";
  if (state === "wait") return "Sırada";
  return state || "";
}
