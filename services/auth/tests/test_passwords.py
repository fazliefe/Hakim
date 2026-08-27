from __future__ import annotations

from auth.passwords import (
    MIN_PASSWORD_LENGTH,
    hash_password,
    password_too_short,
    verify_password,
)


def test_hash_password_has_expected_format() -> None:
    stored = hash_password("gizli-sifre-123")
    scheme, iterations, salt, digest = stored.split("$", 3)
    assert scheme == "pbkdf2"
    assert iterations.isdigit()
    assert len(salt) == 32  # secrets.token_hex(16) -> 32 hex chars
    assert len(digest) == 64  # sha256 digest -> 32 bytes -> 64 hex chars


def test_hash_password_uses_a_random_salt_each_time() -> None:
    # Aynı parola iki kez hash'lenince FARKLI çıktı üretmeli — salt'sız/sabit
    # salt'lı bir regresyon, aynı parolayı her zaman aynı hash'e çevirirdi
    # (rainbow table saldırısına açık kapı).
    first = hash_password("ayni-parola")
    second = hash_password("ayni-parola")
    assert first != second


def test_verify_password_accepts_the_correct_password() -> None:
    stored = hash_password("dogru-parola")
    assert verify_password("dogru-parola", stored) is True


def test_verify_password_rejects_a_wrong_password() -> None:
    stored = hash_password("dogru-parola")
    assert verify_password("yanlis-parola", stored) is False


def test_verify_password_rejects_malformed_stored_values() -> None:
    # Beklenmeyen bir format (eksik alan, tanınmayan şema, sayısal olmayan
    # iterasyon) exception fırlatmak yerine sessizce False dönmeli —
    # store.py bunu doğrudan bir "giriş başarısız" olarak ele alıyor.
    assert verify_password("x", "not-a-valid-stored-hash") is False
    assert verify_password("x", "bcrypt$10$salt$digest") is False
    assert verify_password("x", "pbkdf2$yirmi-bin$salt$digest") is False
    assert verify_password("x", "") is False


def test_password_too_short_boundary() -> None:
    assert password_too_short("a" * (MIN_PASSWORD_LENGTH - 1)) is True
    assert password_too_short("a" * MIN_PASSWORD_LENGTH) is False


def test_password_too_short_handles_empty_and_none() -> None:
    assert password_too_short("") is True
    assert password_too_short(None) is True  # type: ignore[arg-type]
