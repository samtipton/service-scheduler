# Publish email

Send a “schedule published” email from the web app with the Legal-landscape PDF attached. The PDF already exists (`/schedules/<id>/pdf/`). This feature is the send.

Open: template, and whether active-user emails go in BCC.

# Publish email template

The webapp should have a "messages" tab in the top nav that takes you to a page to manage schedule email messages. Inside the messages tab there should be a subtab for "email". 

Inside Email there should be a side nav menu that includes "templates". 

The template creation page should include fields for Subject and body. The fields should support place holders e.g. {{month}} {{year}}. Recipients are all active members of the group that schedule is created on. Subject can be 1 line, body should be a multiline text area. Placeholder help text in both.

Inside Email there should be a side nav menu that includes "sent" that contains records of sent emails, when they were sent (datetime), recipients, subject, body. Just like a normal email app.

Inside Email there should be a side nav menu that includes "new email" (at the top). here we can select a schedule and a template and click send. Make it look like an email app as much as possible. Template values should get filled in from the selected scheduled for a preview view.

Inside email there should be a side nav menu that includes "reminders". This is a placeholder for the future email reminder feature configuration menu.

Include a button in the overlay in month_schedule.html to send the schedule. The button should pop up a modal that has an email compose type UI like the one in the messages > email page. You can select a template, schedule is the one we were just looking at, see the preview of the template rendered, see recipient list etc, and a send button and a cancel button

# Unknowns

How do we connect the email account that will send the message. Is this possible to do without buying a email account? Can I use my personal gmail? 

How do we render the schedule html that is necessary to render the schedule pdf so we don't have to go through the calendar menu?

## Done when

A scheduler can send the current month PDF to the roster without leaving the app.

## Steps

Rough order. Mail goes out through Brevo’s transactional API from this machine. No deploy and no SMTP key. The PDF is rendered on the server the way `schedules.views.pdf` already does. The schema below is approved and migrated (`messaging.0001_email_template_and_sent_email`).

### App

Messaging is its own Django app, `messaging`. It does not live in `core` or `schedules`. `core` is seed commands and fixtures. `schedules` is the solver, the month grid, and the PDF.

The package is `messaging`, not `messages`. `django.contrib.messages` already uses the app label `messages`. The nav label stays Messages and the routes stay `/messages/`.

`messaging` owns `EmailTemplate`, `SentEmail`, the Messages pages, and the Brevo call. It depends on `schedules` and `users`. PDF rendering stays in `schedules/services/pdf.py`; messaging calls `render_schedule_pdf`. The month-grid button posts to a messaging URL, so schedule views do not import messaging models.

- [x] Add `messaging` to `INSTALLED_APPS` with its own models, views, templates, and urls. Include those urls at `/messages/`.

### Mail account

The Brevo account already exists. From address is `olsenparkannouncements@gmail.com`. The app stores a restricted Brevo API key, not an SMTP key and not the Gmail password. The laptop calls `https://api.brevo.com/v3/smtp/email`. Brevo sends the message. A home IP is enough: the API key learns the address it is called from, and blocking of unknown IPs stays off until 30 days pass with no new address. An SMTP key has no learning phase, so leave SMTP blocking off and do not create an SMTP key. The free plan is about 300 emails a day and prints a small “Sent with Brevo” line.

- [x] Brevo sender is `olsenparkannouncements@gmail.com`. The Restricted API key is in `.env` as `BREVO_API_KEY`. `.env` is gitignored. Permissions are Transactional email = All and Transactional SMS = Read/write, with every other resource at None. SMTP IP blocking stays off.
- [x] Read `BREVO_API_KEY` with `python-decouple`, same as `POSTGRES_PASSWORD`. From address is `olsenparkannouncements@gmail.com`. When the key is missing, print the message and do not call Brevo. Tests fake the HTTP call.

### Data

The publish roster is the active members of the schedule's group. Each user already has a required unique email. Send puts the From address in To and the roster in BCC so members do not see each other.

- [x] `EmailTemplate`: `name`, `subject` (one line), `body` (text), `created_by` → User, `created_at`, `updated_at`.
- [x] `SentEmail`: `schedule` → Schedule, `template` → EmailTemplate (null if the template is deleted), rendered `subject` and `body` stored as sent, `sent_at`, `sent_by` → User, `recipients` text snapshot of the BCC addresses.
- [x] Replace only `{{month}}` and `{{year}}` from `schedule.date` (`%B` and `%Y`). Leave every other character as typed.

### PDF

`views.pdf` already renders `schedules/pdf_month_schedule.html` with inlined `schedule.css` and `pdfkit` (Legal, landscape). The calendar page only starts the download.

- [x] Move that context build and `pdfkit.from_string` into `schedules/services/pdf.py` as `render_schedule_pdf(schedule) -> bytes`. The download view returns those bytes. The send path calls the same function, with no browser and no calendar menu.

### Safety

Lifted. Send mails every active user. To is the From address. The roster is BCC. When groups exist, limit that roster to the schedule's group. Send test email still posts to one address typed into Test recipient, on both New email and the month-grid modal.

- [x] Enforce the roster BCC in the send function and in tests. Inactive users are left off. The test button still sends to one typed address.

### Send

- [x] Add the send function in `messaging`: load the schedule and template, fill the placeholders, and POST the PDF as a base64 attachment named `schedule-<month>-<year>.pdf`. To = the From address, BCC = the active emails, split so each attached message stays at or under 99 recipients. Write `SentEmail` after the requests succeed. On a failed first request, show the error and leave no sent row.
- [x] Any logged-in user may send, matching PDF and Generate. A scheduler role waits on accounts. `LoginRequiredMiddleware` only guards `/schedules/`, so guard `/messages/` the same way.

### Messages UI

`templates/base.html` is the page title and the user menu. The month grid is its own document and does not extend it.

- [x] Add a Messages link on the `base.html` toolbar. Routes live under `/messages/` and require login.
- [x] The Messages page has an Email subtab. Inside Email, a side nav: New email (top), Templates, Sent, Reminders.
- [x] Templates: list, create, edit. Subject is a single line. Body is a textarea. Both show help text for `{{month}}` and `{{year}}`.
- [x] New email looks like a compose window: pick a schedule and a template, show the filled subject and body, list the recipients, then Send.
- [x] Sent lists datetime, recipients, and subject, and opens one record to the stored body. Read-only.
- [x] Reminders is a static placeholder page for `docs/features/reminders.md`. It does not send.

### Month grid

- [x] Add a Send schedule button in the overlay in `month_schedule.html`, next to Download PDF. It opens a modal with the same compose fields. The schedule is this month. The user picks a template, sees the preview and the recipient list, then Send or Cancel.
- [x] Share one partial for those compose fields so the modal and New email stay the same. Post to the same preview and send views, with the CSRF token.

### Tests

- [x] Cover placeholder fill, inactive users left off the BCC list, the PDF bytes on the message (mock `pdfkit.from_string`), a `SentEmail` row only after a successful send, a preview that does not send, the reminders page, and an anonymous `/messages/` request redirecting to login. Tag test users `test+…@`.
