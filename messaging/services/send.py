from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from messaging.models import SentEmail
from messaging.services.brevo import FROM_EMAIL, BrevoError, post_email
from messaging.services.placeholders import fill_placeholders
from messaging.services.recipients import active_roster, bcc_chunks
from schedules.services.pdf import pdf_filename, render_schedule_pdf


class NotOneAddress(Exception):
    pass


def rendered_message(schedule, template):
    return (
        fill_placeholders(template.subject, schedule),
        fill_placeholders(template.body, schedule),
    )


def parse_test_address(raw):
    """One plain email address. Empty, lists, and display names are rejected."""
    text = (raw or "").strip()
    if not text or any(ch.isspace() or ch in ",;" for ch in text):
        raise NotOneAddress("Enter one email address.")
    try:
        validate_email(text)
    except ValidationError as exc:
        raise NotOneAddress("Enter one email address.") from exc
    return text


def _deliver(schedule, template, sent_by, recipients):
    subject, body = rendered_message(schedule, template)
    pdf_bytes = render_schedule_pdf(schedule)
    filename = pdf_filename(schedule)
    post_email(
        to=recipients,
        bcc=[],
        subject=subject,
        body=body,
        pdf_bytes=pdf_bytes,
        pdf_name=filename,
    )
    return SentEmail.objects.create(
        schedule=schedule,
        template=template,
        subject=subject,
        body=body,
        sent_by=sent_by,
        recipients="\n".join(recipients),
    )


def send_schedule_email(schedule, template, sent_by):
    """Mail every active user. To is the From address. The roster is BCC.

    The roster is the active members of the schedule's group. Writes one
    SentEmail after every chunk is accepted. A failed first chunk leaves no
    row. A later failure records the addresses already accepted.
    """
    roster_emails = [
        email
        for email in active_roster(schedule.group).values_list("email", flat=True)
        if email != FROM_EMAIL
    ]
    if not roster_emails:
        raise BrevoError("No active members to email.")

    subject, body = rendered_message(schedule, template)
    pdf_bytes = render_schedule_pdf(schedule)
    filename = pdf_filename(schedule)
    sent_bcc = []
    try:
        for chunk in bcc_chunks(roster_emails):
            post_email(
                to=[FROM_EMAIL],
                bcc=chunk,
                subject=subject,
                body=body,
                pdf_bytes=pdf_bytes,
                pdf_name=filename,
            )
            sent_bcc.extend(chunk)
    except BrevoError:
        if sent_bcc:
            SentEmail.objects.create(
                schedule=schedule,
                template=template,
                subject=subject,
                body=body,
                sent_by=sent_by,
                recipients="\n".join(sent_bcc),
            )
        raise
    return SentEmail.objects.create(
        schedule=schedule,
        template=template,
        subject=subject,
        body=body,
        sent_by=sent_by,
        recipients="\n".join(sent_bcc),
    )


def send_test_email(schedule, template, sent_by, address):
    """Send the same message to one typed address. The roster is not included."""
    return _deliver(schedule, template, sent_by, [address])
