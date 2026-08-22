from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage


def smtp_configured() -> bool:
    return bool(os.environ.get("HAKIM_SMTP_HOST", "").strip())


def send_code_email(to_addr: str, code: str, *, kind: str = "verify") -> bool:
    host = os.environ.get("HAKIM_SMTP_HOST", "").strip()
    if not host:
        return False
    port = int(os.environ.get("HAKIM_SMTP_PORT", "587"))
    user = os.environ.get("HAKIM_SMTP_USER", "").strip()
    password = os.environ.get("HAKIM_SMTP_PASSWORD", "").strip()
    sender = os.environ.get("HAKIM_SMTP_FROM", user or "hakim@localhost").strip()
    if kind == "reset":
        subject = "HÂKİM parola sıfırlama kodu"
        body = (
            "Parolanızı sıfırlamak için kodunuz:\n\n"
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
            smtp.login(user, password)
        smtp.send_message(message)
    return True


def send_verification_email(to_addr: str, code: str) -> bool:
    return send_code_email(to_addr, code, kind="verify")
