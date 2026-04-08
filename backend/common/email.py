"""backend/common/email.py — Async email sending via SMTP."""

from __future__ import annotations

import os
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import structlog

logger = structlog.get_logger(__name__)


async def send_email(to: str, subject: str, body: str) -> bool:
    """Send a plain-text email via SMTP. Returns True on success."""
    smtp_host = os.environ.get("SMTP_HOST", "")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASS", "")
    from_addr = os.environ.get("SMTP_FROM", smtp_user)

    if not smtp_host or not smtp_user:
        logger.warning("email_not_configured", reason="SMTP_HOST or SMTP_USER missing")
        return False

    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        import aiosmtplib

        await aiosmtplib.send(
            msg,
            hostname=smtp_host,
            port=smtp_port,
            username=smtp_user,
            password=smtp_pass,
            use_tls=True,
        )
        logger.info("email_sent", to=to, subject=subject)
        return True
    except Exception as exc:
        logger.error("email_send_failed", to=to, error=str(exc))
        return False


async def send_html_email(to: str, subject: str, html_body: str) -> bool:
    """Send an HTML email via SMTP. Returns True on success."""
    smtp_host = os.environ.get("SMTP_HOST", "")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASS", "")
    from_addr = os.environ.get("SMTP_FROM", smtp_user)

    if not smtp_host or not smtp_user:
        logger.warning("html_email_not_configured")
        return False

    msg = MIMEMultipart("alternative")
    msg["From"] = from_addr
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        import aiosmtplib

        await aiosmtplib.send(
            msg,
            hostname=smtp_host,
            port=smtp_port,
            username=smtp_user,
            password=smtp_pass,
            use_tls=True,
        )
        logger.info("html_email_sent", to=to, subject=subject)
        return True
    except Exception as exc:
        logger.error("html_email_send_failed", to=to, error=str(exc))
        return False


async def send_quota_alert_email(service_name: str, detail: str | None) -> bool:
    """Send a rate-limit alert email to the admin."""
    admin_email = os.environ.get("ADMIN_ALERT_EMAIL", "")
    if not admin_email:
        logger.debug("quota_alert_email_skipped", reason="ADMIN_ALERT_EMAIL not set")
        return False

    subject = f"[TrendScope] API Rate Limit Alert: {service_name}"
    body = (
        f"Service: {service_name}\n"
        f"Type: Rate Limit (429)\n"
        f"Detail: {detail or 'N/A'}\n\n"
        f"Please check the admin dashboard for more details.\n"
        f"Dashboard: /admin/quota-alerts"
    )
    return await send_email(admin_email, subject, body)
