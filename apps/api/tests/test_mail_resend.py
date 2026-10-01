"""Resend outbound mail sender."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.mail import (
    ResendMailSender,
    body_for_delivery,
    outbound_mail_configured,
)


def test_body_for_delivery_strips_draft_banner():
    body = "DRAFT — not sent automatically.\n\nClaim details here."
    assert body_for_delivery(body) == "Claim details here."


def test_resend_sender_posts_to_resend_api():
    sender = ResendMailSender(
        api_key="re_test",
        from_address="Shiprate <disputes@example.com>",
        default_reply_to="disputes@example.com",
    )
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_client = MagicMock()
    mock_client.post.return_value = mock_response
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)

    with patch("app.services.mail.httpx.Client", return_value=mock_client):
        sender.send(
            to_address="billing@carrier.test",
            subject="Billing dispute",
            body="DRAFT — not sent automatically.\n\nPlease review.",
            reply_to="disputes@example.com",
        )

    mock_client.post.assert_called_once()
    args, kwargs = mock_client.post.call_args
    assert args[0] == "https://api.resend.com/emails"
    payload = kwargs["json"]
    assert payload["from"] == "Shiprate <disputes@example.com>"
    assert payload["to"] == ["billing@carrier.test"]
    assert payload["reply_to"] == "disputes@example.com"
    assert "DRAFT" not in payload["text"]


@pytest.mark.parametrize(
    "key,from_addr,expected",
    [
        (None, "a@b.com", False),
        ("re_x", None, False),
        ("re_x", "disputes@b.com", True),
    ],
)
def test_outbound_mail_configured(monkeypatch: pytest.MonkeyPatch, key, from_addr, expected):
    from app.config import settings

    monkeypatch.setattr(settings, "resend_api_key", key, raising=False)
    monkeypatch.setattr(settings, "dispute_from_email", from_addr, raising=False)
    assert outbound_mail_configured() is expected
