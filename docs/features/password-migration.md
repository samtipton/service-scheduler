# Password stand-in after a dump restore

Not a schema migration. Do not run `makemigrations` or `migrate` for this. The `password` column already exists. A `pg_dump` copies the values that are in it.

## Why

`seed_users` stores a hash of the shared `DEFAULT_USER_PASSWORD` on every non-superuser. Django already hashes it. Hashing it again, or mixing the default with the email, still leaves one formula that opens every seeded account. The laptop database keeps those hashes so local logins keep working. The host must not.

## Unusable password

`User.set_unusable_password()` does not invent a password. It sets `password` to `!` plus 40 random characters (`make_password(None)`). A real Django hash never starts with `!`, so `check_password` fails for every typed value. The old password is not recoverable from that string. Nothing is written until `save()`.

`has_usable_password()` is then false. The public forgot-password form does not mail those accounts. That is deliberate: the form must not reveal which addresses exist. The Logins page does mail them. Submitting a person who still has no usable password sends one set-password link. They choose a password before the first login. Change password stays behind a signed-in session, so it cannot be the first step.

A login created from the Logins page already calls `set_unusable_password()`. `seed_users` does not.

## Host steps

Do this on the host database after the dump is restored. Do not run it on the laptop.

1. Restore the dump. Do not commit the dump. `schedules/fixtures/compare/live.sql` is an older fixture, not this copy.
2. The host env has no `DEFAULT_USER_PASSWORD` and no `MY_PASSWORD`. `DEBUG` is false, so `seed_users` refuses to run unless `--force` is passed. Do not pass `--force`.
3. For each user whose password still matches the shared default, call `set_unusable_password()` and save `password`. Leave anyone who already chose their own password. A match is `user.check_password` against the known default, not a guess at the hash.
4. Set a new password on the one superuser on that database. The dump still has the laptop superuser hash.
5. Deactivate logins that should not sign in.
6. Do not email the roster as part of this. When someone needs a login, a group admin resubmits them on Logins and the existing set-password mail goes out.

```python
from django.contrib.auth import get_user_model

User = get_user_model()
for user in User.objects.all():
    if user.check_password("the-shared-default"):
        user.set_unusable_password()
        user.save(update_fields=["password"])
```

Run that with the host `DJANGO_SETTINGS_MODULE` pointed at the restored database. Then set the superuser password in a separate step, not with the shared default.
