import { describe, expect, it } from "vitest";
import {
  calendarLabel,
  durationUnitLabel,
  formatTurkishDate,
  hopStateLabel,
  hopTitle,
  titleCaseLabel,
} from "./labels";

describe("formatTurkishDate", () => {
  it("formats an ISO date into Turkish long form", () => {
    expect(formatTurkishDate("2026-08-27")).toBe("27 Ağustos 2026");
  });

  it("returns an em dash for missing input", () => {
    expect(formatTurkishDate(undefined)).toBe("—");
    expect(formatTurkishDate(null)).toBe("—");
    expect(formatTurkishDate("")).toBe("—");
  });

  it("returns the raw value when it doesn't match the ISO date shape", () => {
    expect(formatTurkishDate("not-a-date")).toBe("not-a-date");
  });

  it("returns the raw value for an out-of-range month instead of crashing", () => {
    expect(formatTurkishDate("2026-13-01")).toBe("2026-13-01");
  });
});

describe("durationUnitLabel", () => {
  it("maps English and Turkish unit spellings to the Turkish label", () => {
    expect(durationUnitLabel("day")).toBe("gün");
    expect(durationUnitLabel("days")).toBe("gün");
    expect(durationUnitLabel("gün")).toBe("gün");
    expect(durationUnitLabel("WEEK")).toBe("hafta");
    expect(durationUnitLabel("month")).toBe("ay");
    expect(durationUnitLabel("years")).toBe("yıl");
  });

  it("falls back to the raw value for an unknown unit", () => {
    expect(durationUnitLabel("fortnight")).toBe("fortnight");
  });

  it("falls back to an empty string for missing input", () => {
    expect(durationUnitLabel(undefined)).toBe("");
    expect(durationUnitLabel(null)).toBe("");
  });
});

describe("calendarLabel", () => {
  // Regresyon: backend'in deadline/engine.py::CalendarType değerleri
  // (criminal/civil/administrative) eskiden bu sözlükte yoktu ve ham
  // İngilizce değer arayüze sızıyordu (bkz. labels.ts'teki yorum).
  it("maps every backend CalendarType value used by services/deadline/engine.py", () => {
    expect(calendarLabel("criminal")).toBe("Ceza Takvimi");
    expect(calendarLabel("civil")).toBe("Hukuk Takvimi");
    expect(calendarLabel("administrative")).toBe("İdari Takvim");
  });

  it("still maps the legacy business/calendar values", () => {
    expect(calendarLabel("business")).toBe("İş Günü");
    expect(calendarLabel("calendar")).toBe("Takvim Günü");
  });

  it("falls back to the raw value for an unmapped calendar type", () => {
    expect(calendarLabel("lunar")).toBe("lunar");
  });
});

describe("titleCaseLabel", () => {
  it("title-cases Turkish words using Turkish casing rules", () => {
    expect(titleCaseLabel("istinaf başvurusu")).toBe("İstinaf Başvurusu");
  });

  it("keeps small connector words lowercase unless they lead the phrase", () => {
    expect(titleCaseLabel("ceza ve hukuk davası")).toBe("Ceza ve Hukuk Davası");
  });

  it("capitalizes a connector word when it is the first word", () => {
    expect(titleCaseLabel("ve diğerleri")).toBe("Ve Diğerleri");
  });
});

describe("hopTitle", () => {
  it("maps a known id directly", () => {
    expect(hopTitle("bm25")).toBe("Metin Taraması");
    expect(hopTitle("rerank")).toBe("Sıralama");
  });

  it("falls back to matching the fallback text when the id is unknown", () => {
    expect(hopTitle("unknown-id", "BM25 arama")).toBe("Metin Taraması");
    expect(hopTitle("unknown-id", "vektor benzerlik")).toBe("Yakın Hüküm");
  });

  it("suppresses internal infra names instead of leaking them to the UI", () => {
    expect(hopTitle("unknown-id", "LangGraph node")).toBe("");
    expect(hopTitle("unknown-id", "groq çağrısı")).toBe("");
  });

  it("title-cases the fallback text when nothing else matches", () => {
    expect(hopTitle("unknown-id", "serbest metin")).toBe("Serbest Metin");
  });
});

describe("hopStateLabel", () => {
  it("maps every known state", () => {
    expect(hopStateLabel("done")).toBe("Tamam");
    expect(hopStateLabel("error")).toBe("Hata");
    expect(hopStateLabel("wait")).toBe("Sırada");
  });

  it("falls back to the raw value for an unknown state", () => {
    expect(hopStateLabel("mystery")).toBe("mystery");
  });
});
