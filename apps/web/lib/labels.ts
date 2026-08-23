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

export function hopTitle(id?: string, fallback?: string): string {
  if (id === "sorgu") return "Soru";
  if (id === "bm25") return "Metin taraması";
  if (id === "vektor") return "Yakın hüküm";
  if (id === "rrf") return "Birleşim";
  if (id === "cevap") return "Cevap";
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
