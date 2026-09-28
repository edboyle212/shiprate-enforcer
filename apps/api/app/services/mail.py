"""Outbound mail port — Resend when configured, else log-only for dev."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Protocol

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_DRAFT_PREFIX = re.compile(r"^DRAFT[^\n]*\n+", re.IGNORECASE)


@dataclass
class MailSend:
    to_address: str
    subject: str
    body: str
    reply_to: str | None = None


class MailDeliveryError(Exception):
    pass


class MailSender(Protocol):
    def send(self, *, to_address: str, subject: str, body: str, reply_to: str | None = None) -> None: ...


def body_for_delivery(body: str) -> str:
    """Strip dev draft banner before carrier delivery."""
    return _DRAFT_PREFIX.sub("", body, count=1).strip() or body


def outbound_mail_configured() -> bool:
    return bool(settings.resend_api_key and settings.dispute_from_email)


def outbound_mail_from_address() -> str | None:
    if not outbound_mail_configured():
        return None
    return settings.dispute_from_email


@dataclass
class LogMailSender:
    sent: list[MailSend] = field(default_factory=list)

    def send(self, *, to_address: str, subject: str, body: str, reply_to: str | None = None) -> None:
        record = MailSend(
            to_address=to_address,
            subject=subject,
            body=body_for_delivery(body),
            reply_to=reply_to,
        )
        self.sent.append(record)
        logger.info(
            "dispute mail logged (not delivered) to=%s reply_to=%s subject=%s",
            to_address,
            reply_to,
            subject,
        )


@dataclass
class ResendMailSender:
    api_key: str
    from_address: str
    default_reply_to: str | None = None

    def send(self, *, to_address: str, subject: str, body: str, reply_to: str | None = None) -> None:
        payload: dict = {
            "from": self.from_address,
            "to": [to_address],
            "subject": subject,
            "text": body_for_delivery(body),
        }
        effective_reply = reply_to or self.default_reply_to
        if effective_reply:
            payload["reply_to"] = effective_reply
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        if response.status_code >= 400:
            detail = response.text[:500]
            raise MailDeliveryError(f"resend_failed:{response.status_code}:{detail}")
        logger.info("dispute mail sent via Resend to=%s subject=%s", to_address, subject)


_log_sender = LogMailSender()
_resend_sender: ResendMailSender | None = None


def get_mail_sender() -> MailSender:
    global _resend_sender
    if outbound_mail_configured():
        if _resend_sender is None:
            _resend_sender = ResendMailSender(
                api_key=settings.resend_api_key or "",
                from_address=settings.dispute_from_email or "",
                default_reply_to=settings.dispute_reply_to or settings.dispute_from_email,
            )
        return _resend_sender
    return _log_sender


def default_mail_sender() -> LogMailSender:
    """Tests inject LogMailSender; production uses get_mail_sender()."""
    return _log_sender
