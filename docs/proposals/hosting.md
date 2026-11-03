# Hosting

Where a Django and Postgres app can run, and where `send_due_reminders` can run when the laptop is asleep. Prices were read in November 2026. Recheck before buying.

What the app actually needs:

- Postgres with backups.
- A clock other than the laptop. `send_due_reminders` is sendable after the configured America/Chicago time on the day before the service, and it is skipped once that service date arrives. Default clock is 6:00 PM, so a Sunday service sends on Saturday evening, a Wednesday service on Tuesday evening, and a weekly task on its own eve (Tuesday when the slot is Wednesday). One run a day, every day, after that clock, covers all three. That run gets one try: a failure, or a clock set later than the job, waits until the next day, and the next day skips. A job every few minutes is slack for a changed clock and for a retry the same evening. It is not a separate requirement.
- `wkhtmltopdf` on the web process. `pdfkit` shells out to that binary for the grid PDF and the publish email. The reminder command does not render a PDF. `pip install` does not provide the binary.

What is a hosting choice, not a requirement:

- An always-on web process. Reminders do not run inside it. A process that sleeps and wakes on the next visit still serves the grid. The first load is slow. People publish and generate only while it is awake.
- Auto-deploy when `main` changes. The PaaS hosts below do this. A VPS does it only if a GitHub Action SSHs in and pulls.
- A Docker image. That is how a buildpack host installs `wkhtmltopdf`. On a VPS, `apt install wkhtmltopdf` and a venv with `requirements.txt` are enough. PuLP's CBC solver comes with the pip package.

`docs/features/reminders.md` named Render as the plan. This file is the comparison, including DigitalOcean. Nothing is deployed yet. `docs/proposals/before-deploy.md` is the work that has to land first.

## Comparison

| | Render | Railway | Fly.io | DigitalOcean App Platform |
|---|---|---|---|---|
| Deploy on push | Connect GitHub. Push to `main` deploys. | Same. | A GitHub Action runs `fly deploy`. | Connect GitHub, GitLab, or Bitbucket. Push deploys. |
| Stays awake | Paid web service does. The free web service sleeps after about 15 minutes. | Hobby services stay up. Sleep is optional. | A Machine stays up if you do not scale it to zero. | A paid container stays up. The free tier is static sites only, so it cannot run Django. |
| Small web price | Starter, 512 MB, about $7 a month. | Hobby is $5 a month and includes $5 of usage, then CPU and RAM are metered. A small always-on app is often $5 to $15. | A shared 512 MB Machine is about $3 to $4 a month. | Shared 512 MiB container, $5 a month, 50 GiB transfer. The next size, 1 GiB, is $10 or $12. |
| Postgres | Managed, from about $6 a month (256 MB) with backups. The free database expires after 30 days. | In the same project, billed on usage (CPU, RAM, disk). | Managed Postgres starts near $38 a month. Postgres you run on a volume is a few dollars and the backups are yours to do. | A development database is $7 a month (512 MiB) and DigitalOcean labels it for development. Managed Postgres for production starts around $15 a month. |
| Cron | A cron service. Billed for the seconds the command runs. `*/5 * * * *` is a small add-on if the command exits quickly. | Cron is built in, billed as usage. | A second Machine, or a scheduled Machine. No first-class cron. | A scheduled Job. Jobs use a container size, so price a frequent job as runtime, not as a free timer. |
| HTTPS and domain | Included on the paid service. | Included. | Included. | Included on paid containers. |
| Secrets | Dashboard env vars. `.env` stays gitignored. | Same, and a hard spending cap. | `fly secrets`. | App-level env vars. |
| Bill shape | Flat per service. Easiest to predict. | Metered, with a cap. | Metered. Cheap compute, expensive managed database. | Flat per container. The database is the large line. |
| Rough month for this app | About $13 to $15. Web $7, database $6, cron pennies to a couple of dollars. | Often $10 to $20, depending on idle CPU. | About $45 with managed Postgres, or under $10 if we operate Postgres ourselves. | About $20 to $27 with a $5 web container and managed Postgres near $15. The $5 + $7 development database is cheaper and is the wrong database for the live grid. |

## What does not fit

- Render's free web service and free database. The site would sleep, and the database goes away.
- DigitalOcean's free tier. It serves static files. This app is Django.
- A VPS as the default when deploy-on-push and managed backups matter. The machine can install `wkhtmltopdf`, run Postgres on localhost, and run the daily command from cron. You patch the OS, take the database backups, and put a web server in front. That checklist is `docs/proposals/before-deploy.md`, under "If the host is a VM."
- Fly.io as the default. The compute is cheap. The managed database is not, and the deploy is a workflow we maintain.

## Choice this comparison supports

Render is the choice. About $13 to $15 a month: a persistent Starter web service (512 MB, about $7), managed Postgres (Basic-256, about $6, backups included), and a daily cron after 6:00 PM Chicago for `send_due_reminders`. Push to `main` deploys. The image is a Dockerfile so the web process has `wkhtmltopdf`. The free web service and the free database are out.

A sleeping web service would still send reminders, and a VPS could install `wkhtmltopdf` without Docker. Neither is the plan. Railway is the spending-cap alternative. DigitalOcean is the alternative when the rest of the account already lives there, on Managed Postgres, not the $7 development database. Fly.io costs more once the database is managed.

Generate runs CBC inside the web request, a few seconds of CPU and RAM, with no queue. Two of those at once can stall the small instance. Cell edits are small writes and are fine together. A one-at-a-time solve, a separate worker, or a larger instance waits until the site actually has overlapping heavy use. The first deploy does not include that work.

Do not create the host until `docs/proposals/before-deploy.md` is done.
