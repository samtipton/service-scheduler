import json
import urllib.error
import urllib.request
from base64 import b64encode

from django.conf import settings

FROM_EMAIL = "olsenparkannouncements@gmail.com"
FROM_NAME = "Olsen Park"
API_URL = "https://api.brevo.com/v3/smtp/email"


class BrevoError(Exception):
    pass


def post_email(*, to, bcc, subject, body, pdf_bytes, pdf_name):
    api_key = settings.BREVO_API_KEY
    if not api_key:
        print("BREVO_API_KEY is missing; email not sent")
        raise BrevoError("Email is not configured.")
    if settings.TESTING and api_key != "test-key":
        raise BrevoError("Refusing to call Brevo during tests.")

    payload = {
        "sender": {"name": FROM_NAME, "email": FROM_EMAIL},
        "to": [{"email": email} for email in to],
        "subject": subject,
        "textContent": body,
        "attachment": [
            {"content": b64encode(pdf_bytes).decode("ascii"), "name": pdf_name}
        ],
    }
    if bcc:
        payload["bcc"] = [{"email": email} for email in bcc]

    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "accept": "application/json",
            "content-type": "application/json",
            "api-key": api_key,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise BrevoError(detail or str(exc.reason)) from exc
    return json.loads(raw) if raw else {}
