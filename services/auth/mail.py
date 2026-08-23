from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage


def smtp_configured() -> bool:
    return bool(os.environ.get("HAKIM_SMTP_HOST", "").strip())


def send_code_email(
    to_addr: str,
    code: str,
    *,
    kind: str = "verify",
    username: str = "",
    password: str = "",
) -> bool:
    host = os.environ.get("HAKIM_SMTP_HOST", "").strip()
    if not host:
        return False
    port = int(os.environ.get("HAKIM_SMTP_PORT", "587"))
    user = os.environ.get("HAKIM_SMTP_USER", "").strip()
    smtp_password = os.environ.get("HAKIM_SMTP_PASSWORD", "").strip()
    sender = os.environ.get("HAKIM_SMTP_FROM", user or "hakim@localhost").strip()
    if kind == "reset":
        subject = "HÂKİM parola sıfırlama kodu"
        body = (
            "Parolanızı sıfırlamak için kodunuz:\n\n"
            f"    {code}\n\n"
            "Kod 15 dakika geçerlidir. Bu isteği siz yapmadıysanız yok sayın.\n"
        )
    elif kind == "invite":
        subject = "HÂKİM hesap daveti"
        credentials = ""
        if username or password:
            credentials = (
                f"Kullanıcı adı: {username or '-'}\n"
                f"Geçici parola: {password or '-'}\n\n"
            )
        body = (
            "Yönetici sizin için bir HÂKİM hesabı oluşturdu.\n\n"
            f"{credentials}"
            "E-postanızı doğrulamak için kodunuz:\n\n"
            f"    {code}\n\n"
            "Kod 15 dakika geçerlidir. Doğruladıktan sonra "
            "yukarıdaki parola ile giriş yapın.\n"
        )
    elif kind == "email_change":
        subject = "HÂKİM e-posta değişikliği"
        body = (
            "E-posta adresinizi güncellemek için kodunuz:\n\n"
            f"    {code}\n\n"
            "Kod 15 dakika geçerlidir. Bu isteği siz yapmadıysanız yok sayın.\n"
        )
    else:
        subject = "HÂKİM e-posta doğrulama kodu"
        body = (
            "Hesabınızı doğrulamak için kodunuz:\n\n"
            f"    {code}\n\n"
            "Kod 15 dakika geçerlidir. Bu isteği siz yapmadıysanız yok sayın.\n"
        )
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = to_addr
    message.set_content(body)
    with smtplib.SMTP(host, port, timeout=12) as smtp:
        smtp.starttls()
        if user:
            smtp.login(user, smtp_password)
        smtp.send_message(message)
    return True


def send_password_email(to_addr: str, username: str, password: str) -> bool:
    host = os.environ.get("HAKIM_SMTP_HOST", "").strip()
    if not host:
        return False
    port = int(os.environ.get("HAKIM_SMTP_PORT", "587"))
    user = os.environ.get("HAKIM_SMTP_USER", "").strip()
    smtp_password = os.environ.get("HAKIM_SMTP_PASSWORD", "").strip()
    sender = os.environ.get("HAKIM_SMTP_FROM", user or "hakim@localhost").strip()
    message = EmailMessage()
    message["Subject"] = "HÂKİM geçici parolanız"
    message["From"] = sender
    message["To"] = to_addr
    message.set_content(
        "Yönetici hesabınız için geçici bir parola gönderdi.\n\n"
        f"Kullanıcı adı: {username}\n"
        f"Parola: {password}\n\n"
        "Giriş yaptıktan sonra parolanızı Ayarlar menüsünden değiştirin.\n"
    )
    with smtplib.SMTP(host, port, timeout=12) as smtp:
        smtp.starttls()
        if user:
            smtp.login(user, smtp_password)
        smtp.send_message(message)
    return True


def send_verification_email(to_addr: str, code: str) -> bool:
    return send_code_email(to_addr, code, kind="verify")
