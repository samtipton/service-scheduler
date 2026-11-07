# Invites

Not built. The shipped group and role rules are in `CONTEXT.md`.

An invite for someone who has no login needs an `Invitation` row (email, group, role, token, invited_by, created_at, expires_at, accepted_at) before a migration. A new address would open a page to set first name, last name, and password, then join the group. An address that already has a login would open a page that says they were invited to join that group, with a link on to `/schedules/`. Do not migrate that until it is approved.

Adding an existing login from the Groups page sends no mail. That part is shipped. Open signup is out of scope.
