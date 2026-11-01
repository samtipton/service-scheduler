# Reminders

Email and text from the app of upcoming schedule assignments.

Within `/messages/email/reminders` (page exists) and `/messages/sms/reminders` (to be built) there should be a control plane where we can configure automated email and/or sms reminders.

The configurable parameters for these are:

1. template message (with {{}} placeholders like with email messages, for task

## Unknowns

### SMS Credits

Sending SMS on brevo requires "credits" you purchase. Can these be purchased programatically?

### Transactional SMS

If someone replies to a text, can that be forwarded to someone to see? E.g. someone says, "Sorry, but I am out of town I need someone to fill my spot", can that be forwarded to someone so it doesn't get lost?

## Done when

Each assigned person gets a reminder before the service, using the Assignment rows for that month.
