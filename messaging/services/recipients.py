from django.contrib.auth import get_user_model

# Brevo allows 99 recipients on one message that has an attachment.
ATTACHMENT_RECIPIENT_LIMIT = 99


def active_roster():
    """Active users with an email.

    When groups exist, this becomes the active members of the schedule's group.
    """
    User = get_user_model()
    return User.objects.filter(is_active=True).exclude(email="").order_by(
        "last_name", "first_name", "email"
    )


def roster_label(user):
    return f"{user.first_name} {user.last_name} <{user.email}>"


def bcc_chunks(roster_emails, to_count=1, limit=ATTACHMENT_RECIPIENT_LIMIT):
    """Split BCC addresses so each attached message stays within Brevo's cap."""
    size = limit - to_count
    if size < 1:
        raise ValueError("no room for BCC recipients")
    emails = list(roster_emails)
    return [emails[i : i + size] for i in range(0, len(emails), size)]
