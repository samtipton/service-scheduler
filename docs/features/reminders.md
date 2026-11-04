# Reminders

Email and text from the app of upcoming schedule assignments per user/task.

Given the latest schedule (current month/year), users who are assigned a task should get a 12-24 hour (configurable) heads up via email and/or sms for the task(s) they are assigned. If assigned to multiple tasks, the message should be contain all assignments.

Within `/messages/email/reminders` (page exists) and `/messages/sms/reminders` (to be built) there should be a control plane where we can configure automated email and/or sms reminders.

The configurable parameters for these are:

1. template message (with {{}} placeholders like with email messages, for {{for task in tasks}} (if possible, suggest convention), {{task.name}} and {{service.name}}
2. how long before the day of the service (date, not datetime) in hours OR
3. time of day on the day before the event
4. Tasks excluded to be excluded from reminders. Candidates: Lesson, announcements.
   1. This should be shown with a dropdown where selecting 1 or more tasks adds them to a bulleted list

## Unknowns

### SMS Credits

Sending SMS on brevo requires "credits" you purchase.

Can these be purchased programatically via the API on our UI? Would we have to store credit card info in our db?

Can we show how many credits are left on the account in our UI?

**Answer.** Buy credits in Brevo: account menu → My plan → SMS prepaid credits → Buy credits. Packs start at 100 credits, they do not expire, and the price depends on the destination country (use United States in their calculator). The public API can send SMS and can read the balance. It cannot charge a card. This app stores no card and no Brevo password.

Show the balance on `/messages/sms/reminders`. `GET https://api.brevo.com/v3/account` returns `plan[]`; the entry with `type: "sms"` has `credits`. A successful send also returns `remainingCredits`, `smsCount`, and `usedCredits`. The current `BREVO_API_KEY` is limited to transactional email and transactional SMS. If `GET /account` comes back permission denied, stop and ask before changing the key. Until that call works, show the `remainingCredits` saved from the last send.

### Transactional SMS

If someone replies to a text, can that be forwarded to someone to see? E.g. someone says, "Sorry, but I am out of town I need someone to fill my spot", can that be forwarded to someone so it doesn't get lost?

Can the reply number be configured for 1 or multiple numbers?

**Answer.** A reply has to land as a text on a phone number we choose. Brevo cannot do that. Hitting reply on a Brevo text goes to Brevo's short code. Brevo then delivers the words in one of two places: an email to the account login address, which cannot be changed, or Brevo Conversations after they approve a dedicated number. Their call-forwarding setting is for voice, not texts. The sender field is rewritten to a 5-digit short code, so it cannot be the coordinator's cell.

Two ways actually put the words on a chosen phone:

- Print that number in the message body and tell the person to text it. That is a new text, not a reply to the reminder. Reply still goes to Brevo's short code. No second vendor.
- Send the reminder from a number that forwards inbound texts to the chosen phone. Twilio does this. SendGrid does not. The forward can live in a Twilio function, so this app still has no inbox screen.

v1 does not build a reply screen. Which of those two paths we use is still open.

### What will trigger reminders to be sent out at their configured time?

Cron jobs? How will that work right now as this app is only running locally on my personal machine? That is sometimes sleeping or shutdown.

Do we need to deploy the app somewhere?

**Answer.** Brevo sends when we call the API. It will not hold a reminder and send it later. A management command, `send_due_reminders`, does the clock check and the send. The laptop does not run it.

The command is sendable after the configured Chicago time on the day before the service, and it records a skip once that date has arrived. One run a day, every day, after the default 6:00 PM, lands the Saturday, Tuesday, and Wednesday-eve reminders. A failed run that day is not retried. A run every few minutes is slack for a later clock and for a same-evening retry. The web process is not the clock.

Host choice is `docs/proposals/hosting.md`. Render is the plan: a persistent Starter web service, managed Postgres, and that daily cron, about $13 to $15 a month. Do not create the host until `docs/proposals/before-deploy.md` is done.

### Pending queue

Can our UI show the pending emails/sms queued up for the current schedule?

**Answer.** Yes. Each reminders page lists one row per person per service date: name, date, tasks, Chicago send time, and status (pending, sent, skipped, failed, or no phone). The list is computed from the schedule the command will use and the saved config. Pending rows are not copied into their own table. `ReminderDelivery` is written when a send is attempted. The page names that schedule. A month picker can preview another month. It does not change what sends.

### What locks a schedule in?

What action will "lock in" the current schedule and create the scheduled tasks?

**Answer.** Nothing is armed. Turning a channel on is the only switch. While email or SMS reminders are enabled, the command reads the most recently created schedule for the current month, and the most recently created schedule for the next month. "Most recent" is greatest `created_at` among schedules whose `date` falls in that month. Grid edits do not move `created_at`, so typing in an older schedule does not make it current. Creating a newer schedule for that month does, including an empty one.

The source schedule is the latest `created_at` for that group's month. There is no official flag.

The command does not copy assignments and does not create one cron job per person. A grid edit on the current schedule before the send changes the message. A successful send writes `ReminderDelivery` and is not repeated for that person, service date, and channel, even if a newer schedule is created later. A disabled channel sends nothing.

## Decisions

These are the choices the steps below implement.

- One reminder per person per calendar date, per channel. Sunday 9:00, Sunday 10:30, and a weekly task dated that same Sunday are one message. Wednesday is its own message because it has its own date.
- Weekly tasks use the grid date `get_service_day` already picks: the Sunday of that week when that Sunday is in the month, otherwise the first in-month service day (Wednesday). A first week with no Sunday still gets a reminder, on Tuesday, at the configured time. June 2026 starts Monday, so that week's weekly assignments are dated Wednesday June 3 and the reminder goes Tuesday June 2. July 2026 starts Wednesday, so they are dated Wednesday July 1 and the reminder goes Tuesday June 30, from July's schedule. A month that starts Thursday, Friday, or Saturday has no Sunday and no Wednesday in the first week, so that stub week has no weekly slot.
- The service date is the grid date stored on `Assignment.assigned_at` (midnight UTC). Send times are America/Chicago wall times. `TIME_ZONE` stays `UTC`. `Service.start_time` is not the offset; it is only available as `{{service.time}}`.
- Each channel has its own template, timing, and exclusion list. Both can be enabled. A user with no phone is skipped for SMS and still gets email.
- Exclusions start empty. Lesson and Announcements are the likely picks, and the dropdown labels them with the service because several tasks share those names (`first_lesson`, `lesson`, `wednesday_lesson`, `announcements`, `wednesday_announcements`).
- Inactive users are left off, same as publish email.
- Reminders go to each assigned person directly. Publish email stays a separate BCC of the whole roster with the PDF.

## Done when

Each assigned person gets a reminder before the service, using the Assignment rows for that month.

## Steps

Schema changes stay manual-approve. The models are specified here. Add them to README Models and migrate only after that schema is approved. One migration: `messaging.0002_reminders`.

Placeholder syntax for reminder bodies (a small renderer in `messaging`, not Django templates, and not the publish-email `{{month}}` / `{{year}}` replacer):

```
{{first_name}}, you are scheduled for {{date}}.

{{#tasks}}
- {{task.name}} — {{service.name}}
{{/tasks}}
```

Outside the block: `{{first_name}}`, `{{last_name}}`, `{{date}}` (`Sunday, November 8`). One `{{#tasks}}` … `{{/tasks}}` block, repeated per assignment that day. Inside the block: `{{task.name}}`, `{{service.name}}`, `{{service.time}}` (`Service.start_time`, `9:00 AM`). Any other `{{…}}` is left as typed. In an email subject, the block flattens to a comma-separated list. SMS has no subject.

Timing, in America/Chicago, from the grid date `D` on `assigned_at`. Subtracting hours from the UTC timestamp is the wrong clock.

- `time_on_previous_day` at 18:00 → Saturday 6:00 PM for a Sunday service.
- `hours_before_day` of 18 → 18 hours before midnight at the start of `D` → Saturday 6:00 AM. 12 → Saturday noon.

### Schema

`User.phone` — `CharField`, `max_length=32`, `blank=True`, `default=""`. Existing rows get `""`. Stored as E.164 (`+1` and ten digits) when the value can be parsed. Not unique.

`ReminderConfig` — one row per channel, `channel` unique (`email` or `sms`).

- `enabled` bool, default false
- `subject` char, max 200, blank for SMS
- `body` text, blank until saved
- `timing_mode` — `hours_before_day` or `time_on_previous_day` (default)
- `hours_before` positive small int, null. Required in hours mode. Allow 1–36.
- `clock_time` time, null. Required in clock mode. Chicago wall time. Default 18:00 when that mode is saved.
- `sms_sender` char, max 15, blank. Digits. Required before SMS can be enabled.
- `excluded_tasks` M2M to `Task`, blank
- `sms_credits_remaining` float, null, and `sms_credits_checked_at` datetime, null. SMS row only.
- `updated_at`

`ReminderDelivery` — written when a send is attempted.

- `schedule` → Schedule `PROTECT` (the schedule that was current when the row was written), `user` → User `PROTECT`
- `channel` (`email` or `sms`)
- `service_date` date
- `send_at` datetime (UTC)
- `status` — `sending`, `sent`, `skipped`, `failed`
- `subject` char blank, `body` text (the rendered text)
- `sent_at` datetime null
- `provider_id` char blank (Brevo `messageId`)
- `error` text blank
- unique `(user, service_date, channel)`. When `Schedule.group` exists, group joins that key. A newer schedule for the same month must not send the same person the same day again.

`sent` and `skipped` are final. `failed` and a `sending` row older than 15 minutes are retried while the Chicago date is still before `service_date`.

- [ ] After approval of the schema above, add it to README Models and create `messaging.0002_reminders`.

### Phone

`users/models.py` has a phone TODO. `core/fixtures/men.csv` already has a `phone` column. `seed_users` ignores it. The sample rows are empty.

- [ ] Add `User.phone` as specified. Show it on the user admin.
- [ ] On seed, save a parsed phone when the user is created. When the user already exists and `phone` is blank and the CSV cell is non-empty, fill it. Leave a stored phone alone when the CSV cell is empty.

### Due reminders

A pure function in `messaging` takes a schedule, a channel config, and a `now`. It groups that schedule's assignments by `(user, service date)`, drops excluded tasks, inactive users, and dates whose tasks were all excluded. The current schedule for a month is `Schedule.objects.filter(date__year=year, date__month=month).order_by("-created_at").first()`. The command calls this for the Chicago current month and the next month. Add `.filter(group=group)` when `Schedule.group` exists.

- [ ] Compute `send_at` with `zoneinfo` `America/Chicago` as in the examples above. Keep `TIME_ZONE` as `UTC`. Weekly dates stay on the assignment's grid date, so a Wednesday June 3 weekly assignment sends Tuesday June 2, and a Wednesday July 1 weekly assignment sends Tuesday June 30.
- [ ] Return a pending item when no `ReminderDelivery` exists yet for that key, or the existing row is `failed` or a stale `sending`.
- [ ] Mark the item sendable when `send_at <= now` and Chicago today is before `service_date`. Mark it `skip` when Chicago today is on or after `service_date`.
- [ ] SMS items for a user with a blank phone stay visible as `no phone` and are not sent.

### Send

Publish mail stays on `POST /v3/smtp/email` with the PDF. Reminder email is one recipient, plain text, no attachment. SMS uses `POST https://api.brevo.com/v3/transactionalSMS/send` with `type: transactional`, `unicodeEnabled: false`, `sender` from `sms_sender`, and `recipient` as digits with country code. The same missing-key and test-key guards as `post_email`. Tests mock `urlopen` and use `test+…@` addresses.

The command `send_due_reminders` loads the most recent schedule for the current month and for the next month, and for each enabled channel runs the due function. It `get_or_create`s the delivery row in `sending` under the unique key before the HTTP call, then updates it to `sent` or `failed`. A skip writes `skipped` and does not call Brevo. A disabled channel and a missing API key write nothing. With both channels disabled, the command sends nothing.

- [ ] Make the PDF attachment optional on the Brevo email call. Reminder email sets no attachment. Publish email still attaches the PDF.
- [ ] Add the SMS call. Save `remainingCredits` onto the SMS `ReminderConfig` after a send.
- [ ] Add `send_due_reminders`. Two overlapping runs share the unique `sending` row so a person gets one message.
- [ ] Refuse to enable a channel whose template is incomplete: email needs subject and body; SMS needs body and a numeric sender; the active timing field is required. Default `enabled` is false.

### Messages UI

`/messages/` already requires login. The Email tab, side nav, and placeholder page exist (`messaging/templates/messaging/reminders.html`). Channel tabs today are Email only.

- [ ] Turn the Email reminders placeholder into the email control plane: enable, subject, body with the placeholder help above, timing radio (hours before the day, or a time the day before), save.
- [ ] Excluded tasks: a `<select>` of tasks labeled `Task name — Service name` (ids collide on "Lesson" and "Announcements"). Choosing one adds a bullet with a remove control. Save the set on `ReminderConfig.excluded_tasks`.
- [ ] Show the schedule the command will use (newest `created_at` for the selected month) and the pending table from the pending-queue answer. Render each body from the saved template. A month control previews another month and does not change what sends. Say so when reminders are off.
- [ ] Send test: pick one pending person-date, type one address, send that rendered body there. Write no `ReminderDelivery`.
- [ ] Add an SMS tab and `/messages/sms/reminders/` with the same controls, no subject, a sender field, a character count (GSM 160), and the credit balance. Help text: leave the word STOP out of the body, or Brevo treats the message as marketing.
- [ ] On that page, load credits from `GET /v3/account` when the key allows it. Show the last stored `remainingCredits` when it does not. The buy path is a short note pointing at Brevo → My plan, with no card form.
- [ ] Sent and skipped rows for the selected schedule sit under the pending table (time in America/Chicago, status, error).

### Hosting

Deploy on push to a host that stays up. The laptop cron is not the plan.

Render is the host. Connect the GitHub repo and auto-deploy the main branch. Three services in one US region: a persistent Starter web service (512 MB, about $7 a month), managed Postgres (Basic-256, about $6 a month, backups included), and a cron service that runs `python manage.py send_due_reminders` once a day after 6:00 PM Chicago. The month is about $13 to $15. Cron is billed for the seconds it runs. The free web service sleeps and the free database expires, so neither is this app. Publish PDF needs `wkhtmltopdf`, and a Render buildpack does not have it, so the web service is a Dockerfile. `BREVO_API_KEY`, `SECRET_KEY`, and the database URL are host env vars. `.env` stays gitignored.

Railway is the other one to consider. Push to `main` deploys, Postgres sits in the same project, and cron is built in. Hobby is $5 a month including $5 of usage, then CPU and RAM are metered, with a hard spending cap. The bill moves around more than Render's. Pick Railway if that cap matters more than a flat line item.

Fly.io stays awake cheaply (a small Machine is a few dollars) and deploys from a Dockerfile, but auto-deploy is a GitHub Action you write, and managed Postgres starts near $38 a month. Running Postgres yourself on a volume is cheaper and means you own backups.

DigitalOcean App Platform also deploys on push and has managed Postgres. The database is the expensive part (tens of dollars). Use it only if the other accounts already live there.

- [ ] Add a Dockerfile that installs `wkhtmltopdf`, collects static files, and runs gunicorn. `pdfkit` is already how publish email builds the PDF.
- [ ] On Render: persistent Starter web service, managed Postgres, a daily cron after 6:00 PM Chicago for `send_due_reminders`, auto-deploy from `main`, secrets in the dashboard. No sleeping free instance and no free database.

### Tests

- [ ] Cover the renderer (loop, subject flatten, unknown tags left as typed), both send clocks including the Sunday / Saturday 6:00 PM and Saturday 6:00 AM examples, excluded tasks, two tasks the same day in one body, Wednesday as a separate item, the June 2026 Tuesday June 2 weekly reminder and the July 2026 Tuesday June 30 reminder from July's schedule, a newer schedule for the month replacing an older one, a second schedule not re-sending a person/date/channel already sent, inactive users omitted, no-phone SMS, a delivery row only after a mocked accept, a failed first call leaves `failed` and no second send on the success path, skip-on-the-day writes `skipped` and does not call Brevo, send test writes no delivery row, and an anonymous `/messages/sms/reminders/` redirects to login.

### Browser

- [ ] With the dev server, on both reminder pages: save a template, switch timing mode, add and remove an excluded task, confirm the pending rows match the newest schedule for the current month, and send a test to one address. Reload the other channel and confirm its config stayed put.
