from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from auth.mail import smtp_configured
from auth.store import AuthError, UserRecord, get_store

router = APIRouter(prefix="/v1/auth", tags=["auth"])


class LoginBody(BaseModel):
    password: str = Field(min_length=1)
    identifier: str = ""
    email: str = ""
    username: str = ""


class RegisterBody(BaseModel):
    username: str = Field(min_length=3)
    email: str = Field(min_length=5)
    password: str = Field(min_length=6)
    display_name: str = ""


class CreateUserBody(BaseModel):
    username: str = Field(min_length=3)
    email: str = Field(min_length=5)
    password: str = Field(min_length=6)
    display_name: str = ""
    role: str = "user"


class VerifyBody(BaseModel):
    identifier: str = Field(min_length=3)
    code: str = Field(min_length=4)


class ResendBody(BaseModel):
    identifier: str = Field(min_length=3)


class ForgotBody(BaseModel):
    identifier: str = Field(min_length=3)


class ResetBody(BaseModel):
    identifier: str = Field(min_length=3)
    code: str = Field(min_length=4)
    password: str = Field(min_length=6)


def current_user(authorization: str | None = Header(default=None)) -> UserRecord:
    user = get_store().resolve_token(authorization)
    if user is None:
        raise HTTPException(status_code=401, detail="Oturum gerekli.")
    return user


def optional_user(authorization: str | None = Header(default=None)) -> UserRecord | None:
    return get_store().resolve_token(authorization)


def admin_user(user: UserRecord = Depends(current_user)) -> UserRecord:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Yalnızca yönetici.")
    return user


def _auth_error(exc: AuthError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=str(exc))


def _login_id(body: LoginBody) -> str:
    return (body.identifier or body.username or body.email).strip()


@router.post("/login")
def login(body: LoginBody) -> dict[str, Any]:
    try:
        user, token = get_store().login(_login_id(body), body.password)
    except AuthError as exc:
        raise _auth_error(exc) from exc
    return {"token": token, "user": user.to_public()}


@router.post("/register")
def register(body: RegisterBody) -> dict[str, Any]:
    store = get_store()
    try:
        created = store.create_user(
            email=body.email,
            password=body.password,
            display_name=body.display_name,
            username=body.username,
            role="user",
            verified=False,
        )
        code, mailed = store.issue_verification(created.id)
        store.log(created.id, "register", f"{created.username} kayıt oldu")
    except AuthError as exc:
        raise _auth_error(exc) from exc
    payload: dict[str, Any] = {
        "status": "pending_verification",
        "mailed": mailed,
        "smtp": smtp_configured(),
        "user": created.to_public(),
        "message": (
            "Doğrulama kodu e-postanıza gönderildi."
            if mailed
            else "E-posta sunucusu bağlı değil. Kodu aşağıya yazın."
        ),
    }
    if not mailed:
        payload["preview_code"] = code
    return payload


@router.post("/verify")
def verify(body: VerifyBody) -> dict[str, Any]:
    store = get_store()
    try:
        user = store.verify_email(body.identifier, body.code)
        user, token = store.open_session(user)
    except AuthError as exc:
        raise _auth_error(exc) from exc
    return {"token": token, "user": user.to_public()}


@router.post("/resend")
def resend(body: ResendBody) -> dict[str, Any]:
    store = get_store()
    user = store.get_by_identifier(body.identifier)
    if user is None:
        raise HTTPException(status_code=404, detail="Hesap bulunamadı.")
    if user.email_verified:
        raise HTTPException(status_code=400, detail="Bu hesap zaten doğrulanmış.")
    try:
        code, mailed = store.issue_verification(user.id)
    except AuthError as exc:
        raise _auth_error(exc) from exc
    payload: dict[str, Any] = {"mailed": mailed, "smtp": smtp_configured()}
    if not mailed:
        payload["preview_code"] = code
    return payload


@router.post("/forgot")
def forgot(body: ForgotBody) -> dict[str, Any]:
    store = get_store()
    try:
        code, mailed = store.request_password_reset(body.identifier)
    except AuthError as exc:
        raise _auth_error(exc) from exc
    payload: dict[str, Any] = {
        "mailed": mailed,
        "smtp": smtp_configured(),
        "message": (
            "Sıfırlama kodu e-postanıza gönderildi."
            if mailed
            else "E-posta sunucusu bağlı değil. Kodu aşağıya yazın."
        ),
    }
    if not mailed:
        payload["preview_code"] = code
    return payload


@router.post("/reset")
def reset_password(body: ResetBody) -> dict[str, Any]:
    try:
        get_store().reset_password(body.identifier, body.code, body.password)
    except AuthError as exc:
        raise _auth_error(exc) from exc
    return {"status": "ok", "message": "Şifre güncellendi. Yeni şifrenizle giriş yapın."}


@router.post("/logout")
def logout(authorization: str | None = Header(default=None)) -> dict[str, str]:
    get_store().logout(authorization)
    return {"status": "ok"}


@router.get("/me")
def me(user: UserRecord = Depends(current_user)) -> dict[str, Any]:
    return {"user": user.to_public(), "backend": get_store().backend_label()}


@router.get("/users")
def users(_admin: UserRecord = Depends(admin_user)) -> dict[str, Any]:
    rows = []
    store = get_store()
    for user in store.list_users():
        recent = store.list_activity(user_id=user.id, limit=8)
        rows.append({**user.to_public(), "recent": recent})
    return {"users": rows}


@router.post("/users")
def create_user(body: CreateUserBody, admin: UserRecord = Depends(admin_user)) -> dict[str, Any]:
    store = get_store()
    try:
        created = store.create_user(
            email=body.email,
            password=body.password,
            display_name=body.display_name,
            username=body.username,
            role=body.role,
            verified=True,
        )
    except AuthError as exc:
        raise _auth_error(exc) from exc
    store.log(
        admin.id,
        "admin_create_user",
        f"{admin.username} yeni hesap açtı: {created.username} ({created.role})",
    )
    return {"user": created.to_public()}


@router.get("/activity")
def activity(
    user_id: str | None = None,
    limit: int = 200,
    _admin: UserRecord = Depends(admin_user),
) -> dict[str, Any]:
    return {"activity": get_store().list_activity(user_id=user_id, limit=limit)}
