from __future__ import annotations

import json
import os
import re
import secrets
import sqlite3
import string
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from auth.mail import send_code_email, send_password_email, smtp_configured
from auth.passwords import MIN_PASSWORD_LENGTH, hash_password, password_too_short, verify_password

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SQLITE = ROOT / "data" / "accounts.sqlite"
DEFAULT_ADMIN_EMAIL = "hukukcu@hakim.local"
DEFAULT_ADMIN_USERNAME = "admin"
SESSION_DAYS = 14
CODE_MINUTES = 15
USERNAME_RE = re.compile(r"^[a-z0-9_]{3,24}$")
ACTIVITY_REDACT_KEYS = {"query", "answer", "text", "user_text", "content", "draft"}
ACCOUNT_ACTIVITY_KINDS = frozenset(
    {
        "register",
        "login",
        "verify",
        "password_reset_request",
        "password_reset",
        "password_change",
        "email_change_request",
        "email_change",
        "profile_update",
        "session_revoke",
        "admin_create_user",
        "admin_set_role",
        "admin_lock",
        "admin_unlock",
        "admin_delete_user",
        "admin_revoke_sessions",
        "admin_send_password",
    }
)


def _bootstrap_admin_password() -> str:
    """İlk admin hesabı oluşturulurken kullanılacak parola. `HAKIM_ADMIN_PASSWORD`
    set edilmişse onu kullanır; edilmemişse sabit/tahmin edilebilir bir
    varsayılan YERİNE rastgele bir parola üretir ve tek seferlik konsola
    yazdırır (yarışma/production'da unutulmuş bir "admin1234" riskini
    ortadan kaldırmak için — bkz. docs/competition_deployment.md). Yalnızca
    admin hesabı henüz YOKKEN çağrılır (bkz. `ensure_admin`); var olan bir
    hesabın parolasını geriye dönük değiştirmez."""
    env = os.environ.get("HAKIM_ADMIN_PASSWORD", "").strip()
    if env:
        return env
    generated = secrets.token_urlsafe(12)
    print(
        "[hakim-auth] HAKIM_ADMIN_PASSWORD set edilmemiş; ilk admin hesabı için "
        f"rastgele parola üretildi: {generated}\n"
        "[hakim-auth] Bu parolayı not edin (bir daha gösterilmez) veya .env'e "
        "HAKIM_ADMIN_PASSWORD=... ekleyip data/accounts.sqlite dosyasını silerek "
        "yeniden başlatın.",
        file=sys.stderr,
    )
    return generated


class AuthError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class UserRecord:
    id: str
    username: str
    email: str
    display_name: str
    role: str
    created_at: str
    last_login_at: str | None = None
    email_verified: bool = False
    locked: bool = False
    pending_email: str | None = None

    def to_public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "display_name": self.display_name,
            "role": self.role,
            "created_at": self.created_at,
            "last_login_at": self.last_login_at,
            "email_verified": self.email_verified,
            "locked": self.locked,
            "pending_email": self.pending_email,
            "is_admin": self.role == "admin",
        }


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _now_s() -> str:
    return _now().isoformat()


def _session_expires() -> str:
    return (_now() + timedelta(days=SESSION_DAYS)).isoformat()


def _code_expires() -> str:
    return (_now() + timedelta(minutes=CODE_MINUTES)).isoformat()


def _norm_email(email: str) -> str:
    return (email or "").strip().lower()


def _norm_username(username: str) -> str:
    return (username or "").strip().lower()


def _valid_email(email: str) -> bool:
    return "@" in email and "." in email.split("@")[-1]


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _temp_password(length: int = 10) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


class AuthStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path or os.environ.get("HAKIM_AUTH_DB") or DEFAULT_SQLITE)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()
        self.ensure_admin()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS accounts (
                    id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    display_name TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('admin', 'user')),
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_login_at TEXT
                );
                CREATE TABLE IF NOT EXISTS account_sessions (
                    token TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS account_activity (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
                    kind TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    detail TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_activity_created ON account_activity (created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_activity_user ON account_activity (user_id, created_at DESC);
                """
            )
            cols = {row[1] for row in conn.execute("PRAGMA table_info(accounts)")}
            if "username" not in cols:
                conn.execute("ALTER TABLE accounts ADD COLUMN username TEXT")
            if "email_verified" not in cols:
                conn.execute("ALTER TABLE accounts ADD COLUMN email_verified INTEGER NOT NULL DEFAULT 1")
            if "verify_hash" not in cols:
                conn.execute("ALTER TABLE accounts ADD COLUMN verify_hash TEXT")
            if "verify_expires" not in cols:
                conn.execute("ALTER TABLE accounts ADD COLUMN verify_expires TEXT")
            if "locked" not in cols:
                conn.execute("ALTER TABLE accounts ADD COLUMN locked INTEGER NOT NULL DEFAULT 0")
            if "pending_email" not in cols:
                conn.execute("ALTER TABLE accounts ADD COLUMN pending_email TEXT")
            for row in conn.execute("SELECT id, email, username FROM accounts"):
                if row["username"]:
                    continue
                local = _norm_email(row["email"]).split("@")[0]
                candidate = re.sub(r"[^a-z0-9_]", "", local) or "user"
                if len(candidate) < 3:
                    candidate = f"{candidate}user"
                taken = {
                    str(item["username"] or "")
                    for item in conn.execute("SELECT username FROM accounts WHERE username IS NOT NULL")
                }
                name = candidate[:24]
                n = 1
                while name in taken:
                    n += 1
                    name = f"{candidate[:20]}{n}"
                conn.execute("UPDATE accounts SET username = ? WHERE id = ?", (name, row["id"]))
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_accounts_username ON accounts (username COLLATE NOCASE)"
            )
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS account_files (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
                    filename TEXT NOT NULL,
                    mime TEXT NOT NULL DEFAULT '',
                    kind TEXT NOT NULL DEFAULT '',
                    text TEXT NOT NULL DEFAULT '',
                    byte_size INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_files_user ON account_files (user_id, created_at DESC);
                """
            )

    def ensure_admin(self) -> None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id FROM accounts WHERE username = ? OR email = ?",
                (DEFAULT_ADMIN_USERNAME, DEFAULT_ADMIN_EMAIL),
            ).fetchone()
            if row:
                conn.execute(
                    """
                    UPDATE accounts
                    SET username = ?, display_name = ?, email_verified = 1, role = 'admin'
                    WHERE id = ?
                    """,
                    (DEFAULT_ADMIN_USERNAME, "Yönetici", row["id"]),
                )
                return
            conn.execute(
                """
                INSERT INTO accounts (
                    id, email, username, display_name, role, password_hash,
                    created_at, email_verified
                )
                VALUES (?, ?, ?, ?, 'admin', ?, ?, 1)
                """,
                (
                    str(uuid.uuid4()),
                    DEFAULT_ADMIN_EMAIL,
                    DEFAULT_ADMIN_USERNAME,
                    "Yönetici",
                    hash_password(_bootstrap_admin_password()),
                    _now_s(),
                ),
            )

    def _user_from_row(self, row: sqlite3.Row | None) -> UserRecord | None:
        if row is None:
            return None
        keys = row.keys()
        username = str(row["username"]) if "username" in keys and row["username"] else ""
        verified = True
        if "email_verified" in keys:
            verified = bool(row["email_verified"])
        locked = False
        if "locked" in keys:
            locked = bool(row["locked"])
        pending = None
        if "pending_email" in keys and row["pending_email"]:
            pending = str(row["pending_email"])
        return UserRecord(
            id=str(row["id"]),
            username=username,
            email=str(row["email"]),
            display_name=str(row["display_name"]),
            role=str(row["role"]),
            created_at=str(row["created_at"]),
            last_login_at=str(row["last_login_at"]) if row["last_login_at"] else None,
            email_verified=verified,
            locked=locked,
            pending_email=pending,
        )

    def get_by_email(self, email: str) -> UserRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM accounts WHERE email = ?",
                (_norm_email(email),),
            ).fetchone()
        return self._user_from_row(row)

    def get_by_username(self, username: str) -> UserRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM accounts WHERE username = ?",
                (_norm_username(username),),
            ).fetchone()
        return self._user_from_row(row)

    def get_by_identifier(self, identifier: str) -> UserRecord | None:
        raw = (identifier or "").strip()
        if "@" in raw:
            return self.get_by_email(raw)
        return self.get_by_username(raw) or self.get_by_email(raw)

    def get_by_id(self, user_id: str) -> UserRecord | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM accounts WHERE id = ?", (user_id,)).fetchone()
        return self._user_from_row(row)

    def _require_username(self, username: str) -> str:
        name = _norm_username(username)
        if not USERNAME_RE.match(name):
            raise AuthError("Kullanıcı adı 3–24 karakter, yalnızca küçük harf, rakam ve alt çizgi.")
        if name in {DEFAULT_ADMIN_USERNAME, "root", "hakim", "system"}:
            raise AuthError("Bu kullanıcı adı ayrılmıştır.")
        return name

    def create_user(
        self,
        *,
        email: str,
        password: str,
        display_name: str,
        username: str = "",
        role: str = "user",
        verified: bool = False,
    ) -> UserRecord:
        email = _norm_email(email)
        name = (display_name or "").strip() or (username or email.split("@")[0])
        uname = self._require_username(username or re.sub(r"[^a-z0-9_]", "", email.split("@")[0]))
        role = (role or "user").strip().lower()
        if role not in {"admin", "user"}:
            raise AuthError("Rol admin veya user olmalıdır.")
        if not _valid_email(email):
            raise AuthError("Geçerli bir e-posta girin.")
        if email.endswith(".local"):
            raise AuthError("Gerçek bir e-posta kullanın.")
        if password_too_short(password):
            raise AuthError(f"Parola en az {MIN_PASSWORD_LENGTH} karakter olmalıdır.")
        if self.get_by_email(email):
            raise AuthError("Bu e-posta zaten kayıtlı.", 409)
        if self.get_by_username(uname):
            raise AuthError("Bu kullanıcı adı alınmış.", 409)
        user_id = str(uuid.uuid4())
        created = _now_s()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO accounts (
                    id, email, username, display_name, role, password_hash,
                    created_at, email_verified
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, email, uname, name, role, hash_password(password), created, 1 if verified else 0),
            )
        return UserRecord(
            id=user_id,
            username=uname,
            email=email,
            display_name=name,
            role=role,
            created_at=created,
            email_verified=verified,
        )

    def issue_verification(
        self,
        user_id: str,
        *,
        kind: str = "verify",
        password: str = "",
    ) -> tuple[str, bool]:
        code = f"{uuid.uuid4().int % 1_000_000:06d}"
        with self._connect() as conn:
            row = conn.execute(
                "SELECT email, username FROM accounts WHERE id = ?",
                (user_id,),
            ).fetchone()
            if row is None:
                raise AuthError("Hesap bulunamadı.", 404)
            conn.execute(
                "UPDATE accounts SET verify_hash = ?, verify_expires = ? WHERE id = ?",
                (hash_password(code), _code_expires(), user_id),
            )
            email = str(row["email"])
            username = str(row["username"] or "")
        sent = False
        try:
            sent = send_code_email(email, code, kind=kind, username=username, password=password)
        except Exception:
            sent = False
        return code, sent

    def _consume_code(self, identifier: str, code: str) -> UserRecord:
        user = self.get_by_identifier(identifier)
        if user is None:
            raise AuthError("Hesap bulunamadı.", 404)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT verify_hash, verify_expires FROM accounts WHERE id = ?",
                (user.id,),
            ).fetchone()
            if row is None:
                raise AuthError("Hesap bulunamadı.", 404)
            expires = _parse_iso(str(row["verify_expires"] or ""))
            if expires is None or expires < _now() or not row["verify_hash"]:
                raise AuthError("Kodun süresi doldu. Yeni kod isteyin.")
            if not verify_password((code or "").strip(), str(row["verify_hash"])):
                raise AuthError("Kod hatalı.", 401)
            conn.execute(
                """
                UPDATE accounts
                SET email_verified = 1, verify_hash = NULL, verify_expires = NULL
                WHERE id = ?
                """,
                (user.id,),
            )
        found = self.get_by_id(user.id)
        assert found is not None
        return found

    def verify_email(self, identifier: str, code: str) -> UserRecord:
        user = self.get_by_identifier(identifier)
        if user is None:
            raise AuthError("Hesap bulunamadı.", 404)
        if user.email_verified:
            raise AuthError("Bu hesap zaten doğrulanmış. Giriş yapın.")
        verified = self._consume_code(identifier, code)
        self.log(verified.id, "verify", f"{verified.username} e-postasını doğruladı")
        return verified

    def request_password_reset(self, identifier: str) -> tuple[str | None, bool]:
        user = self.get_by_identifier(identifier)
        if user is None:
            return None, smtp_configured()
        code, sent = self.issue_verification(user.id, kind="reset")
        self.log(user.id, "password_reset_request", f"{user.username} parola sıfırlama istedi")
        return code, sent

    def reset_password(self, identifier: str, code: str, password: str) -> UserRecord:
        if password_too_short(password):
            raise AuthError(f"Parola en az {MIN_PASSWORD_LENGTH} karakter olmalıdır.")
        user = self._consume_code(identifier, code)
        with self._connect() as conn:
            conn.execute(
                "UPDATE accounts SET password_hash = ? WHERE id = ?",
                (hash_password(password), user.id),
            )
            conn.execute("DELETE FROM account_sessions WHERE user_id = ?", (user.id,))
        self.log(user.id, "password_reset", f"{user.username} yeni parola belirledi")
        updated = self.get_by_id(user.id)
        assert updated is not None
        return updated

    def login(self, identifier: str, password: str) -> tuple[UserRecord, str]:
        raw = (identifier or "").strip()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM accounts WHERE username = ? OR email = ?",
                (_norm_username(raw), _norm_email(raw)),
            ).fetchone()
            if row is None or not verify_password(password, str(row["password_hash"])):
                raise AuthError("Kullanıcı adı veya parola hatalı.", 401)
            if not int(row["email_verified"] or 0):
                raise AuthError("Önce e-posta doğrulaması gerekli.", 403)
            locked = int(row["locked"] or 0) if "locked" in row.keys() else 0
            if locked:
                raise AuthError("Hesap kilitli. Yöneticinizle iletişime geçin.", 403)
            user = self._user_from_row(row)
        assert user is not None
        return self.open_session(user)

    def open_session(self, user: UserRecord) -> tuple[UserRecord, str]:
        token = uuid.uuid4().hex + uuid.uuid4().hex
        now = _now_s()
        with self._connect() as conn:
            conn.execute("UPDATE accounts SET last_login_at = ? WHERE id = ?", (now, user.id))
            conn.execute(
                """
                INSERT INTO account_sessions (token, user_id, created_at, expires_at)
                VALUES (?, ?, ?, ?)
                """,
                (token, user.id, now, _session_expires()),
            )
        signed = UserRecord(
            id=user.id,
            username=user.username,
            email=user.email,
            display_name=user.display_name,
            role=user.role,
            created_at=user.created_at,
            last_login_at=now,
            email_verified=True,
            locked=False,
        )
        self.log(signed.id, "login", f"{signed.username} oturum açtı")
        return signed, token

    def resolve_token(self, token: str | None) -> UserRecord | None:
        raw = (token or "").strip()
        if raw.lower().startswith("bearer "):
            raw = raw[7:].strip()
        if not raw:
            return None
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT a.* FROM accounts a
                JOIN account_sessions s ON s.user_id = a.id
                WHERE s.token = ? AND s.expires_at > ?
                """,
                (raw, _now_s()),
            ).fetchone()
        user = self._user_from_row(row)
        if user is not None and user.locked:
            return None
        return user

    def logout(self, token: str | None) -> None:
        raw = (token or "").strip()
        if raw.lower().startswith("bearer "):
            raw = raw[7:].strip()
        if not raw:
            return
        with self._connect() as conn:
            conn.execute("DELETE FROM account_sessions WHERE token = ?", (raw,))

    def list_users(self) -> list[UserRecord]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM accounts ORDER BY created_at ASC").fetchall()
        return [item for row in rows if (item := self._user_from_row(row))]

    def _active_admin_count(self, *, exclude_id: str | None = None) -> int:
        sql = "SELECT COUNT(*) AS n FROM accounts WHERE role = 'admin' AND locked = 0"
        params: list[Any] = []
        if exclude_id:
            sql += " AND id != ?"
            params.append(exclude_id)
        with self._connect() as conn:
            row = conn.execute(sql, params).fetchone()
        return int(row["n"] if row else 0)

    def _guard_last_admin(self, user: UserRecord) -> None:
        if user.role != "admin":
            return
        if self._active_admin_count(exclude_id=user.id) < 1:
            raise AuthError("Son yönetici hesabı kaldırılamaz veya kilitlenemez.")

    def session_count(self, user_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS n FROM account_sessions
                WHERE user_id = ? AND expires_at > ?
                """,
                (user_id, _now_s()),
            ).fetchone()
        return int(row["n"] if row else 0)

    def public_user(self, user: UserRecord) -> dict[str, Any]:
        payload = user.to_public()
        payload["session_count"] = self.session_count(user.id)
        return payload

    def update_profile(self, user: UserRecord, *, display_name: str) -> UserRecord:
        name = (display_name or "").strip()
        if len(name) < 2 or len(name) > 80:
            raise AuthError("Görünen ad 2–80 karakter olmalıdır.")
        with self._connect() as conn:
            conn.execute("UPDATE accounts SET display_name = ? WHERE id = ?", (name, user.id))
        self.log(user.id, "profile_update", f"{user.username} görünen adını güncelledi")
        found = self.get_by_id(user.id)
        assert found is not None
        return found

    def change_password(
        self,
        user: UserRecord,
        current_password: str,
        new_password: str,
        *,
        keep_token: str | None = None,
    ) -> UserRecord:
        if password_too_short(new_password):
            raise AuthError(f"Parola en az {MIN_PASSWORD_LENGTH} karakter olmalıdır.")
        with self._connect() as conn:
            row = conn.execute("SELECT password_hash FROM accounts WHERE id = ?", (user.id,)).fetchone()
            if row is None:
                raise AuthError("Hesap bulunamadı.", 404)
            if not verify_password(current_password, str(row["password_hash"])):
                raise AuthError("Mevcut parola hatalı.", 401)
            conn.execute(
                "UPDATE accounts SET password_hash = ? WHERE id = ?",
                (hash_password(new_password), user.id),
            )
        self.revoke_sessions(user.id, except_token=keep_token)
        self.log(user.id, "password_change", f"{user.username} parolasını güncelledi")
        found = self.get_by_id(user.id)
        assert found is not None
        return found

    def request_email_change(self, user: UserRecord, password: str, new_email: str) -> tuple[str, bool]:
        email = _norm_email(new_email)
        if not _valid_email(email):
            raise AuthError("Geçerli bir e-posta girin.")
        if email.endswith(".local"):
            raise AuthError("Gerçek bir e-posta kullanın.")
        if email == _norm_email(user.email):
            raise AuthError("Yeni e-posta mevcut adresle aynı.")
        taken = self.get_by_email(email)
        if taken is not None and taken.id != user.id:
            raise AuthError("Bu e-posta zaten kayıtlı.", 409)
        with self._connect() as conn:
            row = conn.execute("SELECT password_hash FROM accounts WHERE id = ?", (user.id,)).fetchone()
            if row is None:
                raise AuthError("Hesap bulunamadı.", 404)
            if not verify_password(password, str(row["password_hash"])):
                raise AuthError("Parola hatalı.", 401)
        code = f"{uuid.uuid4().int % 1_000_000:06d}"
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE accounts
                SET pending_email = ?, verify_hash = ?, verify_expires = ?
                WHERE id = ?
                """,
                (email, hash_password(code), _code_expires(), user.id),
            )
        sent = False
        try:
            sent = send_code_email(email, code, kind="email_change")
        except Exception:
            sent = False
        self.log(user.id, "email_change_request", f"{user.username} e-posta değişikliği istedi")
        return code, sent

    def confirm_email_change(self, user: UserRecord, code: str) -> UserRecord:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT pending_email, verify_hash, verify_expires FROM accounts WHERE id = ?",
                (user.id,),
            ).fetchone()
            if row is None:
                raise AuthError("Hesap bulunamadı.", 404)
            pending = str(row["pending_email"] or "").strip()
            if not pending:
                raise AuthError("Bekleyen e-posta değişikliği yok.")
            expires = _parse_iso(str(row["verify_expires"] or ""))
            if expires is None or expires < _now() or not row["verify_hash"]:
                raise AuthError("Kodun süresi doldu. Yeni kod isteyin.")
            if not verify_password((code or "").strip(), str(row["verify_hash"])):
                raise AuthError("Kod hatalı.", 401)
            taken = conn.execute(
                "SELECT id FROM accounts WHERE email = ? AND id != ?",
                (pending, user.id),
            ).fetchone()
            if taken is not None:
                raise AuthError("Bu e-posta zaten kayıtlı.", 409)
            conn.execute(
                """
                UPDATE accounts
                SET email = ?, pending_email = NULL, email_verified = 1,
                    verify_hash = NULL, verify_expires = NULL
                WHERE id = ?
                """,
                (pending, user.id),
            )
        self.log(user.id, "email_change", f"{user.username} e-postasını güncelledi")
        found = self.get_by_id(user.id)
        assert found is not None
        return found

    def set_role(self, user_id: str, role: str, actor: UserRecord) -> UserRecord:
        role = (role or "").strip().lower()
        if role not in {"admin", "user"}:
            raise AuthError("Rol admin veya user olmalıdır.")
        user = self.get_by_id(user_id)
        if user is None:
            raise AuthError("Hesap bulunamadı.", 404)
        if user.role == role:
            return user
        if user.role == "admin" and role == "user":
            self._guard_last_admin(user)
        with self._connect() as conn:
            conn.execute("UPDATE accounts SET role = ? WHERE id = ?", (role, user_id))
        self.log(
            actor.id,
            "admin_set_role",
            f"{actor.username} rol değiştirdi: {user.username} -> {role}",
        )
        found = self.get_by_id(user_id)
        assert found is not None
        return found

    def set_locked(self, user_id: str, locked: bool, actor: UserRecord) -> UserRecord:
        user = self.get_by_id(user_id)
        if user is None:
            raise AuthError("Hesap bulunamadı.", 404)
        if actor.id == user_id:
            raise AuthError("Kendi hesabınızı kilitleyemezsiniz.")
        if locked:
            self._guard_last_admin(user)
        with self._connect() as conn:
            conn.execute("UPDATE accounts SET locked = ? WHERE id = ?", (1 if locked else 0, user_id))
        if locked:
            self.revoke_sessions(user_id)
        self.log(
            actor.id,
            "admin_lock" if locked else "admin_unlock",
            f"{actor.username} hesabı {'kilitledi' if locked else 'açtı'}: {user.username}",
        )
        found = self.get_by_id(user_id)
        assert found is not None
        return found

    def delete_user(self, user_id: str, actor: UserRecord) -> None:
        user = self.get_by_id(user_id)
        if user is None:
            raise AuthError("Hesap bulunamadı.", 404)
        if actor.id == user_id:
            raise AuthError("Kendi hesabınızı silemezsiniz.")
        self._guard_last_admin(user)
        with self._connect() as conn:
            conn.execute("DELETE FROM accounts WHERE id = ?", (user_id,))
        self.log(
            actor.id,
            "admin_delete_user",
            f"{actor.username} hesabı sildi: {user.username}",
        )

    def admin_send_password(
        self,
        user_id: str,
        actor: UserRecord,
        *,
        except_token: str | None = None,
    ) -> tuple[str, bool, str | None]:
        target = self.get_by_id(user_id)
        if target is None:
            raise AuthError("Hesap bulunamadı.", 404)
        password = _temp_password()
        with self._connect() as conn:
            conn.execute(
                "UPDATE accounts SET password_hash = ? WHERE id = ?",
                (hash_password(password), target.id),
            )
        self.revoke_sessions(target.id, except_token=except_token)
        preview_code: str | None = None
        sent = False
        try:
            if target.email_verified:
                sent = send_password_email(target.email, target.username, password)
            else:
                preview_code, sent = self.issue_verification(
                    target.id,
                    kind="invite",
                    password=password,
                )
        except Exception:
            sent = False
        self.log(
            actor.id,
            "admin_send_password",
            f"{actor.username} parola e-postası gönderdi: {target.username}",
        )
        return password, sent, preview_code

    def revoke_sessions(self, user_id: str, *, except_token: str | None = None, actor: UserRecord | None = None) -> int:
        raw = (except_token or "").strip()
        if raw.lower().startswith("bearer "):
            raw = raw[7:].strip()
        with self._connect() as conn:
            if raw:
                cur = conn.execute(
                    "DELETE FROM account_sessions WHERE user_id = ? AND token != ?",
                    (user_id, raw),
                )
            else:
                cur = conn.execute("DELETE FROM account_sessions WHERE user_id = ?", (user_id,))
            deleted = int(cur.rowcount or 0)
        if actor is not None:
            target = self.get_by_id(user_id)
            name = target.username if target else user_id
            self.log(actor.id, "admin_revoke_sessions", f"{actor.username} oturumları kapattı: {name}")
        return deleted

    def save_file(
        self,
        user_id: str,
        *,
        filename: str,
        mime: str,
        kind: str,
        text: str,
        byte_size: int,
    ) -> dict[str, Any]:
        file_id = str(uuid.uuid4())
        created = _now_s()
        body = (text or "")[:160000]
        name = (filename or "evrak").strip()[:180] or "evrak"
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO account_files (id, user_id, filename, mime, kind, text, byte_size, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (file_id, user_id, name, (mime or "")[:80], (kind or "")[:24], body, max(0, int(byte_size)), created),
            )
        return self.get_file(user_id, file_id) or {
            "id": file_id,
            "filename": name,
            "mime": mime,
            "kind": kind,
            "byte_size": byte_size,
            "created_at": created,
            "text": body,
        }

    def update_file(
        self,
        user_id: str,
        file_id: str,
        *,
        filename: str,
        text: str,
    ) -> dict[str, Any] | None:
        existing = self.get_file(user_id, file_id)
        if existing is None:
            return None
        body = (text or "")[:160000]
        name = (filename or existing.get("filename") or "evrak").strip()[:180] or "evrak"
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE account_files
                SET filename = ?, text = ?, byte_size = ?
                WHERE id = ? AND user_id = ?
                """,
                (name, body, len(body.encode("utf-8")), file_id, user_id),
            )
        return self.get_file(user_id, file_id)

    def list_files(self, user_id: str, *, limit: int = 40) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, filename, mime, kind, byte_size, created_at, length(text) AS chars
                FROM account_files
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (user_id, max(1, min(limit, 80))),
            ).fetchall()
        return [
            {
                "id": row["id"],
                "filename": row["filename"],
                "mime": row["mime"],
                "kind": row["kind"],
                "byte_size": row["byte_size"],
                "created_at": row["created_at"],
                "chars": row["chars"],
            }
            for row in rows
        ]

    def get_file(self, user_id: str, file_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, filename, mime, kind, text, byte_size, created_at
                FROM account_files
                WHERE id = ? AND user_id = ?
                """,
                (file_id, user_id),
            ).fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "filename": row["filename"],
            "mime": row["mime"],
            "kind": row["kind"],
            "text": row["text"],
            "byte_size": row["byte_size"],
            "created_at": row["created_at"],
        }

    def delete_file(self, user_id: str, file_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM account_files WHERE id = ? AND user_id = ?",
                (file_id, user_id),
            )
            return int(cur.rowcount or 0) > 0

    def log(self, user_id: str, kind: str, summary: str, detail: str | dict[str, Any] | None = None) -> None:
        if isinstance(detail, dict):
            safe = {key: value for key, value in detail.items() if key not in ACTIVITY_REDACT_KEYS}
            payload = json.dumps(safe, ensure_ascii=False)
        else:
            payload = detail if isinstance(detail, str) else json.dumps({}, ensure_ascii=False)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO account_activity (id, user_id, kind, summary, detail, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (str(uuid.uuid4()), user_id, kind, summary[:400], payload[:8000], _now_s()),
            )

    def list_activity(self, *, user_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        kinds = tuple(sorted(ACCOUNT_ACTIVITY_KINDS))
        placeholders = ", ".join("?" for _ in kinds)
        sql = f"""
            SELECT act.*, a.email, a.username, a.display_name, a.role
            FROM account_activity act
            JOIN accounts a ON a.id = act.user_id
            WHERE act.kind IN ({placeholders})
        """
        params: list[Any] = list(kinds)
        if user_id:
            sql += " AND act.user_id = ?"
            params.append(user_id)
        sql += " ORDER BY act.created_at DESC LIMIT ?"
        params.append(max(1, min(limit, 500)))
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            detail: Any = row["detail"]
            try:
                parsed = json.loads(detail) if detail else {}
            except json.JSONDecodeError:
                parsed = {"text": detail}
            out.append(
                {
                    "id": row["id"],
                    "user_id": row["user_id"],
                    "email": row["email"],
                    "username": row["username"],
                    "display_name": row["display_name"],
                    "role": row["role"],
                    "kind": row["kind"],
                    "summary": row["summary"],
                    "detail": parsed,
                    "created_at": row["created_at"],
                }
            )
        return out

    def backend_label(self) -> str:
        mode = "smtp" if smtp_configured() else "local-code"
        return f"sqlite:{self.path.name}:{mode}"


_STORE: AuthStore | None = None


def get_store() -> AuthStore:
    global _STORE
    if _STORE is None:
        _STORE = AuthStore()
    return _STORE


def reset_store() -> None:
    global _STORE
    _STORE = None
