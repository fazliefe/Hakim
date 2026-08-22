"""Account store: SQLite by default, Postgres when HAKIM_DATABASE_URL is reachable."""

from auth.store import (
    AuthError,
    AuthStore,
    UserRecord,
    get_store,
    reset_store,
)

__all__ = ["AuthError", "AuthStore", "UserRecord", "get_store", "reset_store"]
