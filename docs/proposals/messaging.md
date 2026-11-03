# Messaging providers

Comparison for publish email and reminders. Prices were read in November 2026 from vendor pages and, for Brevo SMS, from a reading of Brevo's public credit calculator. Recheck the buy screen before paying. This app sends little mail: one schedule email a month, plus a reminder per assigned person per service. The worked example below is 500 emails and 300 one-segment US texts a month.

The app already sends mail through Brevo (`messaging/services/brevo.py`). Reminders are specified in `docs/features/reminders.md`. A reply to a text has to arrive on a phone we choose. Brevo cannot do that. See that spec.

## Twilio's text pricing

Twilio has no SMS plan and no email product. SendGrid, which Twilio owns, is a separate email bill. Programmable Messaging is pay as you go:

- A US long-code number is $1.15 a month. A toll-free number is $2.15 a month.
- Each SMS segment, in or out, is $0.0083. A segment is 160 GSM characters. A second segment bills again. A failed message adds $0.001.
- US carriers add their own fee on each segment. On a long code that is about $0.0035 (AT&T) to $0.005 (Verizon). One delivered US segment is about $0.012 to $0.013 before the monthly fees.
- A reply that is forwarded to a chosen phone is two messages: the inbound reply, then an outbound copy. Budget about $0.025 for that pair.
- US application-to-person traffic on a 10-digit number has to be registered (A2P 10DLC). Twilio passes the registry fees through. As of their August 2025 table: brand registration $4.50 once for a low-volume brand, or $46 once for a standard brand; campaign vetting $15 once; then a monthly campaign fee of $1.50 (low-volume mixed), $3 (registered 501(c)(3)), or $10 (standard). Which row applies is decided in registration, not by us at send time.
- The card stays on the Twilio account. Nothing in our database.

There is no volume discount at a few hundred texts. The monthly floor is the number plus the campaign fee, about $3 to $12, even in a month we send nothing.

## Email

| | Brevo, current | SendGrid |
|---|---|---|
| Send a transactional email with a PDF and a BCC roster | Yes. Already shipped. | Yes. `POST /v3/mail/send`. New account, new sender check, rewrite the client. |
| One plain-text reminder per person | Yes, same API, no attachment. | Yes. |
| What 500 emails a month costs | $0 on the free plan (300 a day, about 9,000 a month). | $0 for 60 days at 100 a day, then $19.95 a month for 50,000. The old free plan is gone. |
| Footer | Free plan adds "Sent with Brevo". Starter ($9 a month, 5,000 emails) can remove it as a $12 add-on. Standard ($18) removes it. | No Brevo-style footer on the paid plan. |
| Contacts | We do not store a Brevo contact list. The app posts addresses on each send. | Same pattern. Marketing contacts are a separate product and a separate bill. |
| Balance in our UI | Not a credit balance. The free cap is 300 a day. | The API can report usage. We would still build that screen. |

## Text

| | Brevo | Twilio |
|---|---|---|
| Send a US reminder | Yes. Prepaid credits on the account we have. The key already allows transactional SMS. | Yes, after 10DLC registration, which can take days. |
| What 300 one-segment US texts cost | About $3.30. The public calculator prices a US text at 1 credit and 100 credits at $1.09 ($0.0109 each). Credits do not expire. Minimum buy is 100. Confirm on the buy screen; the rate is per country and per segment. | About $4 to $5 in message and carrier fees, plus the monthly floor (number $1.15 and campaign $1.50 to $10). A quiet month still pays that floor. |
| Reply lands on a phone we choose | No. Reply goes to Brevo's short code, then to the login email or to Brevo Conversations. | Yes. An inbound webhook forwards the text to the chosen handset. That forward can be a Twilio function. This app grows no inbox. |
| Put a phone number in the message body | Works, and stays on Brevo. The person must text that number. The phone's reply button still hits Brevo's short code. | Unnecessary if the from-number forwards. |
| Card in our database | No. Buy credits in Brevo. | No. The card is on the Twilio account. |
| Show remaining balance | `GET /v3/account` when the key allows it, and `remainingCredits` on each send. | Twilio's balance API. |

## At 500 emails and 300 US texts

| Stack | Email | Text | Reply on a chosen phone | Rough month |
|---|---|---|---|---|
| Brevo only | Free, with the footer | About $3 in credits | Only if the body tells them to text a number | About $3, plus the credits left sitting in the account |
| Brevo email, Twilio text | Free | About $4 to $5 plus a $3 to $12 floor | Yes | About $10 to $20 |
| SendGrid email, Twilio text | $19.95 after the trial | Same as the Twilio row | Yes | About $30 to $40 |

## Choice this comparison supports

Keep Brevo for email. SendGrid costs $20 a month here and does not send texts. For texts, stay on Brevo if a number printed in the message is enough. Move texts to Twilio only if hitting reply on the reminder must open the coordinator's phone. That choice is still open in `docs/features/reminders.md`.
