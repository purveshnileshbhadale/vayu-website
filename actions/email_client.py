import smtplib
import json
import sys
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


_CONFIG_PATH = _get_base_dir() / "config" / "api_keys.json"


def _load_config() -> dict:
    try:
        return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_config(data: dict):
    try:
        _CONFIG_PATH.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except Exception as e:
        print(f"[Email] Failed to save config: {e}")


_SMTP_DEFAULTS = {
    "gmail.com":    {"host": "smtp.gmail.com",    "port": 587},
    "outlook.com":  {"host": "smtp-mail.outlook.com", "port": 587},
    "hotmail.com":  {"host": "smtp-mail.outlook.com", "port": 587},
    "yahoo.com":    {"host": "smtp.mail.yahoo.com",   "port": 587},
    "icloud.com":   {"host": "smtp.mail.me.com",      "port": 587},
    "zoho.com":     {"host": "smtp.zoho.com",         "port": 587},
    "proton.me":    {"host": "smtp.protonmail.ch",     "port": 587},
}


def email_client(
    parameters: dict = None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params = parameters or {}
    action = params.get("action", "send").strip().lower()

    if player:
        player.write_log(f"[Email] {action}")

    config = _load_config()
    email_config = config.get("email", {})

    if action == "setup":
        addr = params.get("email", "").strip()
        pwd = params.get("password", "").strip()

        if not addr or not pwd:
            return "Email and password are required for setup."

        domain = addr.split("@")[-1].lower()
        smtp = _SMTP_DEFAULTS.get(domain, {"host": f"smtp.{domain}", "port": 587})

        config["email"] = {
            "address": addr,
            "password": pwd,
            "smtp_host": smtp["host"],
            "smtp_port": smtp["port"],
        }
        _save_config(config)
        return f"Email configured for {addr}."

    if action == "send":
        to = params.get("to", "").strip()
        subject = params.get("subject", "").strip()
        body = params.get("body", "").strip()

        if not to:
            return "Recipient email address is required."
        if not subject and not body:
            return "Subject or body is required."

        addr = email_config.get("address", "")
        pwd = email_config.get("password", "")
        host = email_config.get("smtp_host", "smtp.gmail.com")
        port = email_config.get("smtp_port", 587)

        if not addr or not pwd:
            return "Email not configured. Use action=setup first, or provide email/password in config."

        try:
            msg = MIMEMultipart()
            msg["From"] = addr
            msg["To"] = to
            msg["Subject"] = subject or "(No subject)"
            msg.attach(MIMEText(body or "(No body)", "plain", "utf-8"))

            server = smtplib.SMTP(host, port, timeout=30)
            server.starttls()
            server.login(addr, pwd)
            server.send_message(msg)
            server.quit()

            return f"Email sent to {to}."

        except smtplib.SMTPAuthenticationError:
            return (
                "Gmail requires an App Password (not your regular password). "
                "Go to myaccount.google.com/apppasswords to generate one."
            )
        except smtplib.SMTPException as e:
            return f"Failed to send email: {e}"
        except Exception as e:
            return f"Email error: {e}"

    return f"Unknown email action: {action}"
