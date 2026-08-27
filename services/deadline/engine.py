from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from hakim_legal_schema.enums import CalendarType, DurationUnit

# ---------------------------------------------------------------------------
# Resmi tatil takvimi
#
# CMK m.39/4: "Son gün bir tatile rastlarsa süre, tatilin ertesi günü biter."
# HMK m.93:   "...Sürenin son gününün resmî tatil gününe rastlaması hâlinde,
#              süre tatili takip eden ilk iş günü çalışma saati sonunda biter."
# İYUK m.8/2: "...sürenin son günü tatil gününe rastlarsa, süre tatil gününü
#              izleyen çalışma gününün bitimine kadar uzar."
#
# Üç kanun da aynı kuralı koyuyor — sadece CEZA'ya özgü değil. Önceki sürüm
# bu erteleme kuralını yalnızca CalendarType.CRIMINAL için uyguluyordu; bu
# gerçek bir eksiklikti (HUKUK ve İDARE takvimleri de hafta sonu/resmi bayram
# günü erteleme kuralına tabidir), aşağıda tüm takvim türleri için genelleştirildi.
# ---------------------------------------------------------------------------

# Sabit (her yıl aynı takvim günü) resmi tatiller: (ay, gün).
_FIXED_HOLIDAYS: frozenset[tuple[int, int]] = frozenset(
    {
        (1, 1),  # Yılbaşı
        (4, 23),  # Ulusal Egemenlik ve Çocuk Bayramı
        (5, 1),  # Emek ve Dayanışma Günü
        (5, 19),  # Atatürk'ü Anma Gençlik ve Spor Bayramı
        (7, 15),  # Demokrasi ve Millî Birlik Günü
        (8, 30),  # Zafer Bayramı
        (10, 29),  # Cumhuriyet Bayramı
    }
)

# Dini bayramlar (Ramazan/Kurban) her yıl hicri takvime göre kaydığı için
# sabit bir (ay, gün) kuralı yok — yıl başına araştırılmış gerçek tarihler.
# Sadece TAM tatil günleri listelenir; arefe günleri saat 13.00'e kadar
# çalışma günü olduğundan (yarım gün resmi tatil) bilinçli olarak bu tabloya
# DAHİL EDİLMEMİŞTİR — bir sürenin son gününün arefe günü öğleden sonrasına
# denk gelmesi durumunu bu motor şu an ayırt edemez; bu bilinen bir
# basitleştirmedir.
#
# Kaynak: WebSearch ile doğrulanan resmi/haber kaynakları (Diyanet takvimi
# bazlı). 2028 Kurban Bayramı tarihi araştırma sırasında bulunamadı — bu
# yılın kurban bayramı günleri tabloya eklenmedi (eksik veri; motoru yanlış
# tarihle "uydurmak" yerine boş bırakmak tercih edildi).
_RELIGIOUS_HOLIDAYS: dict[int, tuple[date, ...]] = {
    2024: (
        date(2024, 4, 10), date(2024, 4, 11), date(2024, 4, 12),  # Ramazan Bayramı
        date(2024, 6, 16), date(2024, 6, 17), date(2024, 6, 18), date(2024, 6, 19),  # Kurban Bayramı
    ),
    2025: (
        date(2025, 3, 30), date(2025, 3, 31), date(2025, 4, 1),  # Ramazan Bayramı
        date(2025, 6, 6), date(2025, 6, 7), date(2025, 6, 8), date(2025, 6, 9),  # Kurban Bayramı
    ),
    2026: (
        date(2026, 3, 20), date(2026, 3, 21), date(2026, 3, 22),  # Ramazan Bayramı
        date(2026, 5, 27), date(2026, 5, 28), date(2026, 5, 29), date(2026, 5, 30),  # Kurban Bayramı
    ),
    2027: (
        date(2027, 3, 9), date(2027, 3, 10), date(2027, 3, 11),  # Ramazan Bayramı
        date(2027, 5, 16), date(2027, 5, 17), date(2027, 5, 18), date(2027, 5, 19),  # Kurban Bayramı
    ),
    2028: (
        date(2028, 2, 26), date(2028, 2, 27), date(2028, 2, 28),  # Ramazan Bayramı
        # Kurban Bayramı 2028: tarihleri henüz doğrulanamadı, tabloya eklenmedi.
    ),
}

# Bu tablo YIL BAŞINA elle güncellenir (hicri kayma nedeniyle sabit bir
# (ay, gün) kuralı yok, bkz. dosya başındaki not). Kapsam geride kalırsa
# `_next_business_day`/`compute_last_day` SESSİZCE "tatil değil" varsayımına
# düşer — motor çökmez ama bir bayram gününü normal iş günü sayarak son gün
# hesabı ±birkaç gün kayabilir. 2028, Kurban Bayramı doğrulanamadığı için
# tabloda var ama EKSİK — bu yüzden `max(_RELIGIOUS_HOLIDAYS)` yerine son
# TAM kapsanan yıl burada elle belirtiliyor.
LAST_FULLY_COVERED_RELIGIOUS_HOLIDAY_YEAR = 2027
# Süre hesapları tetikleyici tarihten aylar/bir yıl ileriye gidebilir (ör.
# bireysel başvuru süresi 1 yıl); tablo yıl sınırında güvenli kalsın diye en
# az bir sonraki yılı da kapsamalı.
_RELIGIOUS_HOLIDAY_COVERAGE_HORIZON_YEARS = 1


def religious_holiday_table_status(*, today: date | None = None) -> dict[str, Any]:
    """Dini bayram tablosu hâlâ güncel mi? main.py'deki `_check_*`
    fonksiyonlarıyla aynı "canlı kontrol" ilkesi — tablonun var olması
    yetmez, ileriye dönük yeterince GÜNCEL olması gerekir (bkz.
    `/v1/durum` topbar pilleri)."""
    as_of = today or date.today()
    required_through = as_of.year + _RELIGIOUS_HOLIDAY_COVERAGE_HORIZON_YEARS
    ok = LAST_FULLY_COVERED_RELIGIOUS_HOLIDAY_YEAR >= required_through
    detail = (
        "Dini tatil takvimi güncel."
        if ok
        else (
            f"Dini tatil takvimi {LAST_FULLY_COVERED_RELIGIOUS_HOLIDAY_YEAR} sonrasını tam "
            f"kapsamıyor; {required_through} ve sonrasına düşen süre hesapları bayram "
            "günlerini atlamayabilir. services/deadline/engine.py::_RELIGIOUS_HOLIDAYS "
            "güncellenmeli."
        )
    )
    return {
        "ok": ok,
        "last_fully_covered_year": LAST_FULLY_COVERED_RELIGIOUS_HOLIDAY_YEAR,
        "required_through_year": required_through,
        "detail": detail,
    }


# Adli tatil / çalışmaya ara verme dönemi — CMK m.331, HMK m.102, İYUK m.61:
# üçü de aynı takvim aralığını kullanır: 20 Temmuz - 31 Ağustos (dahil).
_ADLI_TATIL_BASLANGIC = (7, 20)
_ADLI_TATIL_BITIS = (8, 31)

# Adli tatile rastlayan sürelerin uzama miktarı takvim türüne göre FARKLIDIR:
# CMK m.331/4: "...tatilin bittiği günden itibaren üç gün uzatılmış sayılır."
# HMK m.104:   "...adli tatilin bittiği günden itibaren bir hafta (7 gün)
#               uzatılmış sayılır."
# İYUK m.8/3:  "...ara vermenin sona erdiği günü izleyen tarihten itibaren
#               yedi gün uzamış sayılır."
_ADLI_TATIL_UZATMA_GUNU: dict[CalendarType, int] = {
    CalendarType.CRIMINAL: 3,
    CalendarType.CIVIL: 7,
    CalendarType.ADMINISTRATIVE: 7,
}


def _is_resmi_tatil(value: date) -> bool:
    if value.weekday() >= 5:  # Cumartesi=5, Pazar=6
        return True
    if (value.month, value.day) in _FIXED_HOLIDAYS:
        return True
    if value in _RELIGIOUS_HOLIDAYS.get(value.year, ()):
        return True
    return False


def _is_adli_tatil(value: date) -> bool:
    start = date(value.year, *_ADLI_TATIL_BASLANGIC)
    end = date(value.year, *_ADLI_TATIL_BITIS)
    return start <= value <= end


def compute_last_day(
    *,
    trigger: date,
    duration: int,
    unit: DurationUnit,
    calendar: CalendarType,
) -> date:
    """Deterministic last day. The model does not calculate time; this function does."""
    last, _note = compute_last_day_detail(trigger=trigger, duration=duration, unit=unit, calendar=calendar)
    return last


def compute_last_day_detail(
    *,
    trigger: date,
    duration: int,
    unit: DurationUnit,
    calendar: CalendarType,
) -> tuple[date, str | None]:
    """Aynı hesap, ama adli tatil/resmi tatil ertelemesi uygulandıysa bunu
    açıklayan bir not da döner — arayüz "14 gün" yazıp son günü 20 gün sonra
    gösterdiğinde, kullanıcı bunun bir hesaplama hatası değil CMK m.331/4 (veya
    HMK m.104/İYUK m.8) uzaması olduğunu görebilsin."""
    if duration < 1:
        raise ValueError("duration must be >= 1")
    if unit is DurationUnit.DAY:
        raw = trigger + timedelta(days=duration)
    elif unit is DurationUnit.WEEK:
        raw = trigger + timedelta(weeks=duration)
    elif unit is DurationUnit.MONTH:
        month = trigger.month - 1 + duration
        year = trigger.year + month // 12
        month = month % 12 + 1
        day = min(trigger.day, _month_days(year, month))
        raw = date(year, month, day)
    elif unit is DurationUnit.YEAR:
        try:
            raw = date(trigger.year + duration, trigger.month, trigger.day)
        except ValueError:
            raw = date(trigger.year + duration, trigger.month, 28)
    else:
        raise ValueError(f"unsupported unit: {unit}")

    last = _next_business_day(raw)
    note: str | None = None
    if last != raw:
        note = f"Ham son gün {raw.isoformat()} resmi tatile denk geldiği için ertesi iş gününe kaydı."

    if _is_adli_tatil(last):
        extension = _ADLI_TATIL_UZATMA_GUNU.get(calendar)
        if extension is not None:
            recess_end = date(last.year, *_ADLI_TATIL_BITIS)
            before_recess_note = last
            last = _next_business_day(recess_end + timedelta(days=extension))
            note = (
                f"Ham hesap {before_recess_note.isoformat()}'e denk gelir; bu tarih adli tatil "
                f"({_ADLI_TATIL_BASLANGIC[1]}.{_ADLI_TATIL_BASLANGIC[0]}–{_ADLI_TATIL_BITIS[1]}.{_ADLI_TATIL_BITIS[0]}) "
                f"içinde kaldığından, tatilin bitişinden itibaren {extension} gün uzayarak {last.isoformat()} olur."
            )

    return last, note


def _month_days(year: int, month: int) -> int:
    if month == 12:
        nxt = date(year + 1, 1, 1)
    else:
        nxt = date(year, month + 1, 1)
    return (nxt - timedelta(days=1)).day


def _next_business_day(value: date) -> date:
    """Roll forward past weekends AND resmi tatil günleri (bkz. dosya başı notu).

    A consecutive block of holidays (e.g. a bayram butting against a weekend)
    is handled by repeatedly advancing a day at a time until a non-holiday
    day is reached, matching "tatilin ertesi günü" / "ilk iş günü" wording.
    """
    while _is_resmi_tatil(value):
        value += timedelta(days=1)
    return value


@dataclass(frozen=True, slots=True)
class DeadlineComputation:
    rule_id: str
    name: str
    trigger: date | None
    duration: int
    unit: DurationUnit
    calendar: CalendarType
    last_day: date | None
    legal_basis: tuple[str, ...]
    missing: str | None = None
    adjustment_note: str | None = None
