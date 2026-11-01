# Accounts

Thin isolation so production and experiments (and later, other congregations) do not share one global roster.

Today: volunteer is the login `User`. Single congregation. No `Church` table.

Group ~= church

## v1

- **User** — login (email). You already have this.
- **Group** — one congregation: services, tasks, people, prefs, schedules separate from the others.
- **Membership** — user ↔ group, role `admin` | `scheduler`.
- **Person** — man on the roster. Not necessarily a login. FK to group.

Scope Service, Task, Preference, Schedule, Assignment by group. Production group holds official months. Person/Church is the durable boundary.

User-email queries follow the schedule’s group. The publish-email roster (`docs/features/email.md`) is the active members of that group, not every `User`. A production schedule does not pick up sandbox addresses, and a sandbox schedule does not pick up production addresses.

## Considerations to verify

Users could technically be part of multiple groups.

I want to know what the data model should look like. Should group be on schedule or on services?

## v1 out of scope

Signup, invites, billing, self-serve preferences, multi-group UI polish. One group + your login is enough to separate sandbox from production.

## Why now

The year comparison test uses the Django test database, so it does not write into Sunday’s grid. Group-scoped rows still matter once a second congregation (or a long-lived experiment) shares the production database.

## Done when

Queries for the month UI use the production group only. An experiment run cannot appear in the solver’s production history. Adding a second group later does not require another data-model rewrite. A schedule’s user-email lookup returns only active members of that schedule’s group.
