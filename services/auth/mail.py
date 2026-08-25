from __future__ import annotations

import html
import os
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path

_LOGO_CID = "hakim-emblem"
_LOGO_PATH = Path(__file__).resolve().parents[2] / "apps" / "web" / "public" / "hakim-emblem.png"


@dataclass(frozen=True)
class MailCopy:
    subject: str
    topic: str
    lead: str
    fields: tuple[tuple[str, str], ...] = ()
    secret_label: str = ""
    secret: str = ""
    closing: str = "Kod on beş dakika süreyle geçerlidir."
    caveat: str = "Bu işlemi siz talep etmediyseniz işbu iletiyi yok sayınız."


def smtp_configured() -> bool:
    return bool(os.environ.get("HAKIM_SMTP_HOST", "").strip())


def _logo_bytes() -> bytes | None:
    try:
        data = _LOGO_PATH.read_bytes()
    except OSError:
        return None
    return data or None


def _plain(copy: MailCopy) -> str:
    lines = [
        "HÂKİM",
        "Hukuki araştırma ve evrak sistemi",
        "",
        f"KONU: {copy.topic}",
        "",
        "Sayın ilgilisi,",
        "",
        copy.lead,
        "",
    ]
    for label, value in copy.fields:
        lines.append(f"{label}: {value}")
    if copy.fields:
        lines.append("")
    if copy.secret:
        lines.extend([copy.secret_label or "Kod", copy.secret, ""])
    lines.extend(
        [
            copy.closing,
            "",
            copy.caveat,
            "",
            "Saygılarımızla,",
            "HÂKİM",
        ]
    )
    return "\n".join(lines)


def _html(copy: MailCopy) -> str:
    field_rows = ""
    for label, value in copy.fields:
        field_rows += (
            "<tr>"
            f'<td style="padding:10px 0 2px;font-size:11px;letter-spacing:0.12em;'
            f'text-transform:uppercase;color:#6f5210">{html.escape(label)}</td>'
            "</tr><tr>"
            f'<td style="padding:0 0 8px;font-size:16px;color:#1c160c;'
            f'font-family:Georgia,\'Times New Roman\',serif">{html.escape(value)}</td>'
            "</tr>"
        )
    secret_block = ""
    if copy.secret:
        secret_block = (
            f'<p style="margin:22px 0 8px;font-size:11px;letter-spacing:0.14em;'
            f'text-transform:uppercase;color:#6f5210">{html.escape(copy.secret_label or "Kod")}</p>'
            '<div style="border:1px solid #c4a035;background:#fffdf6;padding:14px 16px;text-align:center">'
            f'<span style="font-family:Consolas,\'Courier New\',monospace;font-size:26px;'
            f'letter-spacing:0.28em;color:#1c160c;font-weight:700">{html.escape(copy.secret)}</span>'
            "</div>"
        )
    return f"""<!DOCTYPE html>
<html lang="tr">
<body style="margin:0;padding:0;background:#e8dfc8">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#e8dfc8">
    <tr>
      <td align="center" style="padding:28px 12px">
        <table role="presentation" width="560" cellpadding="0" cellspacing="0"
          style="width:560px;max-width:560px;background:#f7f1e4;border:1px solid #c4a035">
          <tr>
            <td style="height:6px;background:#b8962c;font-size:0;line-height:0">&nbsp;</td>
          </tr>
          <tr>
            <td align="center" style="padding:28px 36px 8px">
              <img src="cid:{_LOGO_CID}" width="72" height="72" alt="HÂKİM" style="display:block;border:0">
              <p style="margin:14px 0 0;font-family:Georgia,'Times New Roman',serif;font-size:22px;
                letter-spacing:0.28em;color:#6f5210">HÂKİM</p>
              <p style="margin:6px 0 0;font-size:11px;letter-spacing:0.16em;text-transform:uppercase;
                color:#7a7164">Hukuki araştırma ve evrak sistemi</p>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 36px 0">
              <div style="height:1px;background:#c4a035;opacity:0.55"></div>
            </td>
          </tr>
          <tr>
            <td style="padding:22px 36px 8px;font-family:Georgia,'Times New Roman',serif;color:#1c160c">
              <p style="margin:0 0 18px;font-size:11px;letter-spacing:0.14em;text-transform:uppercase;color:#6f5210">
                Konu: {html.escape(copy.topic)}
              </p>
              <p style="margin:0 0 14px;font-size:16px">Sayın ilgilisi,</p>
              <p style="margin:0;font-size:15px;line-height:1.65">{html.escape(copy.lead)}</p>
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-top:8px">
                {field_rows}
              </table>
              {secret_block}
              <p style="margin:20px 0 0;font-size:14px;line-height:1.6;color:#3d3428">{html.escape(copy.closing)}</p>
              <p style="margin:10px 0 0;font-size:13px;line-height:1.55;color:#6a5f4e">{html.escape(copy.caveat)}</p>
              <p style="margin:28px 0 0;font-size:15px">Saygılarımızla,</p>
              <p style="margin:4px 0 0;font-size:13px;letter-spacing:0.18em;color:#6f5210">HÂKİM</p>
            </td>
          </tr>
          <tr>
            <td style="padding:18px 36px 24px;font-size:11px;line-height:1.5;color:#8a7d6a;
              font-family:Georgia,'Times New Roman',serif">
              Bu ileti HÂKİM sisteminden otomatik olarak düzenlenmiştir. Lütfen yanıtlamayınız.
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _deliver(to_addr: str, copy: MailCopy) -> bool:
    host = os.environ.get("HAKIM_SMTP_HOST", "").strip()
    if not host:
        return False
    port = int(os.environ.get("HAKIM_SMTP_PORT", "587"))
    user = os.environ.get("HAKIM_SMTP_USER", "").strip()
    smtp_password = os.environ.get("HAKIM_SMTP_PASSWORD", "").strip()
    sender = os.environ.get("HAKIM_SMTP_FROM", user or "hakim@localhost").strip()
    message = EmailMessage()
    message["Subject"] = copy.subject
    message["From"] = sender
    message["To"] = to_addr
    message.set_content(_plain(copy))
    message.add_alternative(_html(copy), subtype="html")
    logo = _logo_bytes()
    if logo:
        html_part = message.get_payload()[1]
        html_part.add_related(logo, maintype="image", subtype="png", cid=_LOGO_CID)
    with smtplib.SMTP(host, port, timeout=12) as smtp:
        smtp.starttls()
        if user:
            smtp.login(user, smtp_password)
        smtp.send_message(message)
    return True


def send_code_email(
    to_addr: str,
    code: str,
    *,
    kind: str = "verify",
    username: str = "",
    password: str = "",
) -> bool:
    if kind == "reset":
        copy = MailCopy(
            subject="HÂKİM — Parola sıfırlama",
            topic="Parola sıfırlama talebi",
            lead="Hesabınız için bir parola sıfırlama talebi alınmıştır. İşlemi tamamlamak üzere aşağıda kayıtlı kodu kullanınız.",
            secret_label="Sıfırlama kodu",
            secret=code,
        )
    elif kind == "invite":
        fields: list[tuple[str, str]] = []
        if username:
            fields.append(("Kullanıcı adı", username))
        if password:
            fields.append(("Geçici parola", password))
        copy = MailCopy(
            subject="HÂKİM — Hesap daveti",
            topic="Hesap daveti",
            lead="Yönetici tarafından adınıza bir HÂKİM hesabı açılmıştır. E-posta doğrulamasını tamamladıktan sonra aşağıda bildirilen geçici parola ile sisteme giriş yapınız.",
            fields=tuple(fields),
            secret_label="Doğrulama kodu",
            secret=code,
            closing="Kod on beş dakika süreyle geçerlidir. İlk girişin ardından parolanızı Ayarlar menüsünden değiştiriniz.",
            caveat="Bu daveti beklemiyorsanız işbu iletiyi yok sayınız.",
        )
    elif kind == "email_change":
        copy = MailCopy(
            subject="HÂKİM — E-posta değişikliği",
            topic="Kayıtlı e-posta adresinin güncellenmesi",
            lead="Kayıtlı e-posta adresinizin değiştirilmesi talep edilmiştir. Onayı tamamlamak üzere aşağıda kayıtlı kodu kullanınız.",
            secret_label="Onay kodu",
            secret=code,
        )
    else:
        copy = MailCopy(
            subject="HÂKİM — E-posta doğrulama",
            topic="E-posta adresinin doğrulanması",
            lead="HÂKİM hesabınızın e-posta doğrulamasını tamamlamak üzere aşağıda kayıtlı kodu kullanınız.",
            secret_label="Doğrulama kodu",
            secret=code,
        )
    return _deliver(to_addr, copy)


def send_password_email(to_addr: str, username: str, password: str) -> bool:
    copy = MailCopy(
        subject="HÂKİM — Geçici parola",
        topic="Geçici parola tebliği",
        lead="Yönetici, hesabınız için yeni bir geçici parola düzenlemiştir. Mevcut parola bu işlemle geçersiz hale gelir.",
        fields=(
            ("Kullanıcı adı", username),
            ("Geçici parola", password),
        ),
        closing="Sisteme giriş yaptıktan sonra parolanızı Ayarlar menüsünden değiştiriniz.",
        caveat="Bu talebi siz iletmediyseniz derhal yöneticinize bildiriniz.",
    )
    return _deliver(to_addr, copy)


def send_verification_email(to_addr: str, code: str) -> bool:
    return send_code_email(to_addr, code, kind="verify")
