from __future__ import annotations

from datetime import date

from deadline.engine import CalendarType, DurationUnit, compute_last_day


def test_criminal_deadline_moves_off_weekend() -> None:
    # Trigger deliberately kept outside the 20 Temmuz-31 Ağustos adli tatil
    # window so this test isolates the plain weekend-rollover behaviour
    # (see the dedicated adli-tatil tests below for that separate rule).
    # 2026-11-12 (Thu) + 2 gün = 2026-11-14 (Cumartesi) -> ilk iş günü
    # 2026-11-16 Pazartesi.
    last = compute_last_day(
        trigger=date(2026, 11, 12),
        duration=2,
        unit=DurationUnit.DAY,
        calendar=CalendarType.CRIMINAL,
    )
    assert last == date(2026, 11, 16)


def test_criminal_deadline_friday_plus_one_is_monday() -> None:
    last = compute_last_day(
        trigger=date(2026, 11, 13),
        duration=1,
        unit=DurationUnit.DAY,
        calendar=CalendarType.CRIMINAL,
    )
    assert last == date(2026, 11, 16)
    assert last.weekday() == 0


def test_civil_deadline_also_moves_off_weekend() -> None:
    # HMK m.93: resmi tatil erteleme kuralı sadece ceza takvimine özgü
    # değil — hukuk takvimi de aynı kurala tabi. Trigger, adli tatil
    # penceresinin (20 Temmuz-31 Ağustos) dışında tutuldu ki bu test sadece
    # hafta sonu ertelemesini izole etsin (bkz. aşağıdaki adli-tatil testleri).
    # 2026-11-13 Cuma + 1 gün = 2026-11-14 Cumartesi -> ilk iş günü olan
    # 2026-11-16 Pazartesi'ye erteler.
    last = compute_last_day(
        trigger=date(2026, 11, 13),
        duration=1,
        unit=DurationUnit.DAY,
        calendar=CalendarType.CIVIL,
    )
    assert last == date(2026, 11, 16)


def test_criminal_deadline_moves_off_fixed_resmi_tatil() -> None:
    # 2026-04-22 (Çarşamba) + 1 gün = 2026-04-23 (23 Nisan, resmi tatil,
    # ayrıca Perşembe) -> ertesi iş günü 2026-04-24 Cuma'ya erteler.
    last = compute_last_day(
        trigger=date(2026, 4, 22),
        duration=1,
        unit=DurationUnit.DAY,
        calendar=CalendarType.CRIMINAL,
    )
    assert last == date(2026, 4, 24)


def test_administrative_deadline_moves_off_fixed_resmi_tatil() -> None:
    # İYUK m.8/2 aynı erteleme kuralını idari takvim için de öngörür.
    last = compute_last_day(
        trigger=date(2026, 4, 22),
        duration=1,
        unit=DurationUnit.DAY,
        calendar=CalendarType.ADMINISTRATIVE,
    )
    assert last == date(2026, 4, 24)


def test_deadline_moves_off_religious_holiday() -> None:
    # 2026 Ramazan Bayramı: 20-22 Mart. 2026-03-19 (Perşembe) + 1 gün =
    # 2026-03-20 (bayramın ilk günü, ayrıca Cuma) -> bayram 22 Mart Pazar'da
    # bitiyor (zaten hafta sonu) -> ilk iş günü 2026-03-23 Pazartesi.
    last = compute_last_day(
        trigger=date(2026, 3, 19),
        duration=1,
        unit=DurationUnit.DAY,
        calendar=CalendarType.CIVIL,
    )
    assert last == date(2026, 3, 23)


def test_criminal_deadline_extends_three_days_after_adli_tatil() -> None:
    # CMK m.331/4: adli tatile (20 Temmuz-31 Ağustos) rastlayan süre,
    # tatilin bittiği günden itibaren 3 gün uzatılmış sayılır.
    # 2026-08-10 (Pazartesi) + 14 gün = 2026-08-24 (Pazartesi, adli tatil
    # içinde) -> 31 Ağustos (Pazartesi) + 3 gün = 3 Eylül Perşembe.
    last = compute_last_day(
        trigger=date(2026, 8, 10),
        duration=14,
        unit=DurationUnit.DAY,
        calendar=CalendarType.CRIMINAL,
    )
    assert last == date(2026, 9, 3)


def test_civil_deadline_extends_seven_days_after_adli_tatil() -> None:
    # HMK m.104: adli tatile rastlayan süre, tatilin bittiği günden
    # itibaren bir hafta (7 gün) uzatılmış sayılır.
    last = compute_last_day(
        trigger=date(2026, 8, 10),
        duration=14,
        unit=DurationUnit.DAY,
        calendar=CalendarType.CIVIL,
    )
    assert last == date(2026, 9, 7)


def test_administrative_deadline_extends_seven_days_after_adli_tatil() -> None:
    # İYUK m.8/3 + m.61: çalışmaya ara verme (20 Temmuz-31 Ağustos)
    # dönemine rastlayan süre, ara vermenin bitişinden itibaren 7 gün
    # uzamış sayılır.
    last = compute_last_day(
        trigger=date(2026, 8, 10),
        duration=14,
        unit=DurationUnit.DAY,
        calendar=CalendarType.ADMINISTRATIVE,
    )
    assert last == date(2026, 9, 7)


def test_deadline_before_adli_tatil_window_is_unaffected() -> None:
    # Adli tatil öncesinde biten bir süre uzatmadan etkilenmemeli.
    last = compute_last_day(
        trigger=date(2026, 6, 1),
        duration=10,
        unit=DurationUnit.DAY,
        calendar=CalendarType.CIVIL,
    )
    assert last == date(2026, 6, 11)
