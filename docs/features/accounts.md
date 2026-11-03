# Accounts

Thin isolation so production and experiments (and later, other congregations) do not share one global roster.

Group ~= church. The login `User` is the roster row. There is no `Person` model in this version.

## v1

- **User** — login (email). Already in the tree.
- **Group** — one congregation, `name` only. Other rows store its numeric `id`. The existing congregation is named Olsen Park. There is no slug.
- **Membership** — user ↔ group, role `admin` | `scheduler`. A user can be in more than one group.

Service, Task, TaskPreference, Schedule, and Assignment each take a group. That answers the old question of schedule versus services: the group is on all five, and a row's group follows its parent when a caller omits it.

`Task.id` stays a globally unique code (`song_leader`, `lesson`). Several tasks already share a display name. A sandbox copy cannot reuse `song_leader`. Do not switch the primary key to an AutoField to make room for that.

TaskRequires stays per user and task, with no group column. The solver keeps a row when that person is on the schedule's roster and both tasks are on the services in that solve.

User-email queries follow the schedule’s group. The publish-email roster is the active members of that group, not every `User`. A production schedule does not pick up sandbox addresses, and a sandbox schedule does not pick up production addresses.

A `scheduler` can edit the grid and send mail for their group. An `admin` can change roles, remove someone from that group, or delete the group. Deleting a group deletes its schedules, services, tasks, preferences, assignments, and sent mail for those schedules. User accounts stay. The Groups page states that before the confirm button. A person with neither role, and who is not staff, cannot open the grid. Staff and superuser can still open one, which is the same bypass delete and rename already had.

The top bar remembers one current group. `/schedules` and the new-email schedule list show that group. Creating a group makes the creator its admin. Adding an existing login to the roster sends no mail. Olsen Park's current roster is not emailed.

An invite for someone who has no login is not built. It needs an `Invitation` row (email, group, role, token, invited_by, created_at, expires_at, accepted_at) before a migration. A new address would open a page to set first name, last name, and password, then join the group. An address that already has a login would open a page that says they were invited to join that group, with a link on to `/schedules/`. Do not migrate that until it is approved.

The solver assigns active members when the group has any memberships. A group with none, which is how the test database starts, still uses every active user. After the migration, the real database has a production membership for each existing user, so the solver is scoped.

## v1 out of scope

Open signup, the invite-link page, billing, self-serve preferences, and a `Person` who is on the roster without a login. Change password, set-password by email, and the other gates before a public host are `docs/proposals/before-deploy.md`.

## Why now

The year comparison test uses the Django test database, so it does not write into Sunday’s grid. Group-scoped rows matter once a sandbox dataset shares the production database.

## Done when

Queries for the month UI use that schedule's group. An experiment run cannot appear in the solver’s production history. Adding a second group later does not require another data-model rewrite, except that task codes stay globally unique. A schedule’s user-email lookup returns only active members of that schedule’s group.
