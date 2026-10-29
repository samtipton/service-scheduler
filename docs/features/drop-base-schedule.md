# Drop `base_schedule` and `is_official`

Git-style parent schedules and an official/draft flag. Fairness already reads Assignment dates. These two fields are leftover from an older “selected month” model.

## What they do today

`Schedule.base_schedule` is an optional FK to another schedule. The create-month dialog has a “Base Schedule” dropdown. Generate loads that parent’s Assignment rows into the ILP as locked variables (`x == 1`) so consecutive-week and `rotation_group` can see the previous Sunday (and the last week of the previous month). Year-compare chains months with the same FK. Seed walks the parent pointer. The month UI falls back to the parent’s AssignmentStats when the new month has no rows yet.

`Schedule.is_official` is unused for FairJobs and Catch-up share. History is Assignment rows. The flag still appears in admin, seed (`True` on generated months), `Schedule.__str__` (“Selected” / “Draft”), `select_as_official()`, `get_latest_selected()`, and `generate_assignment_stats()` (only reuse stats from official schedules). `create_from_base()` defaults the parent to `get_latest_selected()` when none is posted; the create view only sets a parent if the form sent one.

If a month is created with no parent, Generate cannot see last month’s last announcements. Consecutive-week’s first pair is then two Sundays *inside* this month, and the handoff at the month line is guesswork.

## Replacement

Look up Assignment rows by calendar date, not by a parent Schedule.

When generating June, load assignments whose `assigned_at` falls in the last week of May (the same window consecutive-week already uses: from `month_start − 7 days`). Lock those as `x == 1`, the same way base rows are locked today. Several schedules for May are fine: use the assignments that exist. No unique `(schedule, task, assigned_at)` yet; if two rows claim the same hole, pick a deterministic one (latest `id` or latest schedule `created_at`) and document it.

Create-month drops the Base Schedule dropdown. `base_schedule` and `is_official` columns go away. AssignmentStats regen stops filtering on official. FairJobs still ignores AssignmentStats.

Year-compare and tests that pass `base_schedule=` switch to the calendar lookback (create May, then June; June’s solve sees May’s assignments by date).

## Out of scope

Charts. Unique assignment keys. Deleting extra schedules for the same month (still allowed). TaskCycle.

## Done when

Generate on a month with no `base_schedule` still respects last month’s last Sunday for consecutive-week and `rotation_group`. The create dialog has no parent picker. Admin has no official flag. `python manage.py test` passes without those fields.
