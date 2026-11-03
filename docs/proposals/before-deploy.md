# Before deploy

What has to be true before this app is on a public host. Hosting itself is `docs/proposals/hosting.md`. Deploy is the last step, not this one.

The code in this list is in the tree. The host is not. Render services are not created from here. What is still open is marked below: rotate or deactivate seeded logins on the production database, set the host env, and turn HSTS on only after HTTPS works.

## Already in the tree

- `/schedules/`, `/messages/`, and `/account/` redirect anonymous requests to `/login/`. `/password_reset/` and `/reset/` stay public.
- Logout, Change password, and (for a group admin) Logins are in the toolbar. Login is `templates/registration/login.html`, and that page links to forgot password.
- There is no public signup.
- `seed_users` creates every non-superuser with `DEFAULT_USER_PASSWORD`. The superuser uses `MY_PASSWORD`. Those commands refuse to run when `DEBUG` is false unless `--force` is passed. The host env must not define either variable.
- Password validators are the Django defaults. Set-password and change-password use them.
- `SECRET_KEY`, `POSTGRES_PASSWORD`, and `BREVO_API_KEY` come from the environment. `.env` is gitignored.
- `is_active` is how a person is left off the email roster. An inactive user also cannot authenticate.

## Groups

`docs/features/accounts.md` is the model. Its v1 left signup out of scope. This proposal does not add open signup. It does require the group boundary before the database is reachable from the internet.

The existing congregation is named Olsen Park. Service, Task, TaskPreference, Schedule, and Assignment take a group. A schedule's mail roster is the active members of that schedule's group. The backfill does not create a second group.

- [x] Approve the schema in `docs/features/accounts.md` (Group, Membership with role `admin` or `scheduler`, group on Service, Task, preference, Schedule, and Assignment). Write it into README Models, then one migration. Applied locally: `users.0002_group_and_membership`, `schedules.0007_group_scope`. `schedules/fixtures/compare/live.sql` predates `group_id`. Regenerate it with `dump_compare_db` before `compare_objectives --dump`. The default tests do not load it.
- [x] Backfill existing rows into the Olsen Park group. The migration also adds a membership there for each user that already exists at migrate time (admin when staff or superuser, otherwise scheduler). It does not create a group named Sandbox. `users.0003` removes the group slug.
- [x] Month list, month grid, solver history, and publish email read only that schedule's group.
- [x] A user who is not a member of the production group gets no production schedule, no production assignment, and no production address on a send. Staff and superuser can still open a grid.
- [x] Tests: a sandbox schedule cannot see production assignments, and a production send cannot include a sandbox address. Tag test users `test+…@`.

## Account creation

An admin of the group creates the login. The person sets their own password after that. There is no page where a stranger registers.

- [x] Group admin can create a user: email, first name, last name. The app sets an unusable password and emails a single-use set-password link. The link is sent through Brevo, the same way a reminder will be, to that one address. Submitting the same new person again resends while the password is still unusable.
- [x] The set-password page and the change-password page use the existing password validators. Change password is linked from the toolbar for a signed-in user.
- [x] Forgot password uses the same Brevo mail path and does not reveal whether the address exists. An address with no usable password gets the same page and no mail.
- [x] A `scheduler` can edit the grid and send mail for their group. An `admin` can also create and deactivate logins. A member with neither role cannot open the grid.
- [ ] Before the host exists, every seeded user either sets a new password or is deactivated. The shared `DEFAULT_USER_PASSWORD` is not a live credential. The host's env has no `DEFAULT_USER_PASSWORD` and no `MY_PASSWORD`. Do this on the production database after migrate. Do not run it against the laptop database. Local logins stay as they are.
- [x] Seed commands refuse to run when `DEBUG` is false unless an explicit flag is passed. The flag is `--force`. `seed_data` passes it through.

## Security audit

These are the holes in the current tree. Close them and re-check. A general scan is not a substitute for this list.

- [x] `DEBUG` and `ALLOWED_HOSTS` are read with python-decouple, the same way `SECRET_KEY` already is. `DEBUG` is false on the host. The debug toolbar is not installed then. While `DEBUG` is true, `?debug=true` turns the toolbar on, and that toolbar shows SQL and settings. The laptop `.env` keeps `DEBUG=True`. `cast=bool` is not used, because the string `"False"` would become true.
- [x] `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` come from the environment. When `DEBUG` is false, `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, and `CSRF_COOKIE_SECURE` are on, and `SECURE_PROXY_SSL_HEADER` trusts Render's `X-Forwarded-Proto`. `SECURE_HSTS_SECONDS` stays 0 until HTTPS is confirmed. Set it in the host env after that, not before.
- [x] Database host, name, user, and password come from the environment. A `DATABASE_URL` that contains `://` is the production database, and a non-local host requires SSL. A bare value such as `localhost` is ignored so the laptop keeps using `POSTGRES_*`.
- [x] `manage.py check --deploy` with `DEBUG=false` leaves two warnings, both chosen. `security.W004` is HSTS, open until HTTPS works. `security.W009` is this laptop's `SECRET_KEY`, which starts with `django-insecure-`. The host key must be long, random, and without that prefix. Do not copy the laptop key.
- [x] `@csrf_exempt` is off `generate_schedule_assignments`, `update_schedule`, and `clear_schedule`. The grid sends `X-CSRFToken` from the page token. A PUT without it returns 403.
- [x] `pdf` no longer uses `@csrf_exempt`.
- [x] `/admin/` stays staff-only. A normal roster user is not staff. The account-creation path sets `is_staff` false.
- [x] Secrets are only in the host's env. A search of tracked files found no live Brevo key, `SECRET_KEY`, or database password. `.env` is gitignored. Set the host values in the Render dashboard. Do not commit them.
- [x] Login, password change, a cross-site grid save (must fail), and a sandbox user opening a production schedule are covered by tests.
- [x] Split `requirements.txt`. The production file installs Django, Postgres, PuLP, pdfkit, and python-decouple. `requirements-dev.txt` adds pytest, black, and django-debug-toolbar. The host image installs the production file only.

## If the host is a VM

Render is the host, so this section does not apply. It stays in case that choice changes. Render terminates HTTPS and does not expose Postgres. A DigitalOcean Droplet or a Linode is a different path: a tutorial that installs nginx on a VM. Do not follow that tutorial unless the PaaS choice is dropped.

- [ ] If a VM is the host, nginx (or Caddy) is the only public listener, Postgres listens on localhost, and the nginx config is reviewed before go-live. A Cloudflare tunnel is one way to avoid opening the firewall. The platform's HTTPS is the way on a PaaS, and a second proxy is not required.
- [ ] The domain registrar is whoever is cheapest for a name, private registration, and mailbox forwarding. That forwarding is not the app's outbound mail. Brevo stays the sender. A referral credit is optional and is not part of this checklist.

## Done when

A person who is not in the production group cannot see or mail that group. The grid writes require the CSRF token. Both are true in the test suite (`python manage.py test`, including the year comparison).

Still before the first public boot: on the production database, every seeded login sets a new password or is deactivated. The host env has `DEBUG=false`, the real `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`, a `DATABASE_URL`, a `SECRET_KEY` that does not start with `django-insecure-`, and no `DEFAULT_USER_PASSWORD` or `MY_PASSWORD`. Leave `SECURE_HSTS_SECONDS` unset until HTTPS answers. Then follow `docs/proposals/hosting.md`. The Dockerfile and the Render services are that next step, not this one.
