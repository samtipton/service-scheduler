# Accounts

Thin isolation so production and experiments (and later, other congregations) do not share one global roster.



Group ~= church

## v1

- **User** — login (email). You already have this.
- **Group** — one congregation: services, tasks, people, prefs, schedules separate from the others.
- **Membership** — user ↔ group, role `admin` | `scheduler`.
- **Person** — man on the roster. Not necessarily a login. FK to group.

Scope Service, Task, Preference, Schedule, Assignment by group. Production group holds official months. An experiment run is either a child of that group (`kind=experiment`) or a second group cloned from it. Year-sandbox.md can ship with `kind` first; Person/Church is the durable boundary.

## v1 out of scope

Signup, invites, billing, self-serve preferences, multi-group UI polish. One group + your login is enough to separate sandbox from production.

## Why now

A year simulation that writes into the same Assignment table as Sunday’s grid will poison fairness. Accounts/group (or at least group -scoped rows) make “production history” a query filter, not a convention.

## Done when

Queries for the month UI use the production group only. An experiment run cannot appear as official or in the solver’s production history. Adding a second group later does not require another data-model rewrite.
