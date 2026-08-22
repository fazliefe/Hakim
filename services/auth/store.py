from __future__ import annotations

import json
import os
import re
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from auth.mail import send_code_email, smtp_configured
from auth.passwords import hash_password, verify_password

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SQLITE = ROOT / "data" / "accounts.sqlite"
DEFAULT_ADMIN_EMAIL = "hukukcu@hakim.local"
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin1234"
SESSION_DAYS = 14
CODE_MINUTES = 15
USERNAME_RE = re.compile(r"^[a-z0-9_]{3,24}$")


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


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


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
                    hash_password(DEFAULT_ADMIN_PASSWORD),
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
        return UserRecord(
            id=str(row["id"]),
            username=username,
            email=str(row["email"]),
            display_name=str(row["display_name"]),
            role=str(row["role"]),
            created_at=str(row["created_at"]),
            last_login_at=str(row["last_login_at"]) if row["last_login_at"] else None,
            email_verified=verified,
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
        if "@" not in email or "." not in email.split("@")[-1]:
            raise AuthError("Geçerli bir e-posta girin.")
        if email.endswith(".local"):
            raise AuthError("Gerçek bir e-posta kullanın.")
        if len(password) < 6:
            raise AuthError("Parola en az 6 karakter olmalıdır.")
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

    def issue_verification(self, user_id: str, *, kind: str = "verify") -> tuple[str, bool]:
        code = f"{uuid.uuid4().int % 1_000_000:06d}"
        with self._connect() as conn:
            row = conn.execute("SELECT email FROM accounts WHERE id = ?", (user_id,)).fetchone()
            if row is None:
                raise AuthError("Hesap bulunamadı.", 404)
            conn.execute(
                "UPDATE accounts SET verify_hash = ?, verify_expires = ? WHERE id = ?",
                (hash_password(code), _code_expires(), user_id),
            )
            email = str(row["email"])
        sent = False
        try:
            sent = send_code_email(email, code, kind=kind)
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

    def request_password_reset(self, identifier: str) -> tuple[str, bool]:
        user = self.get_by_identifier(identifier)
        if user is None:
            raise AuthError("Hesap bulunamadı.", 404)
        code, sent = self.issue_verification(user.id, kind="reset")
        self.log(user.id, "password_reset_request", f"{user.username} parola sıfırlama istedi")
        return code, sent

    def reset_password(self, identifier: str, code: str, password: str) -> UserRecord:
        if len(password) < 6:
            raise AuthError("Parola en az 6 karakter olmalıdır.")
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
        return self._user_from_row(row)

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

    def log(self, user_id: str, kind: str, summary: str, detail: str | dict[str, Any] | None = None) -> None:
        payload = detail if isinstance(detail, str) else json.dumps(detail or {}, ensure_ascii=False)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO account_activity (id, user_id, kind, summary, detail, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (str(uuid.uuid4()), user_id, kind, summary[:400], payload[:8000], _now_s()),
            )

    def list_activity(self, *, user_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        sql = """
            SELECT act.*, a.email, a.username, a.display_name, a.role
            FROM account_activity act
            JOIN accounts a ON a.id = act.user_id
        """
        params: list[Any] = []
        if user_id:
            sql += " WHERE act.user_id = ?"
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
