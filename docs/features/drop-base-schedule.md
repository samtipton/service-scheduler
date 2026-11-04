# Drop `base_schedule` and `is_official`

Done. `schedules.0009_drop_base_schedule_and_is_official` removes both columns. History is Assignment rows. FairJobs still ignores AssignmentStats.

Generate locks assignments whose date falls in the seven days before the month being solved, in that schedule's group. Those rows are `x == 1`, so consecutive-week and `rotation_group` still see the previous Sunday. The schedule being solved is excluded. Two rows for the same day and task: the later schedule `created_at` wins, then the higher assignment id. An assignment older than that week is history for fairness and is not locked.

The create-month dialog has no Base Schedule picker. Admin has no official flag. A new month does not borrow another schedule's AssignmentStats. Seed no longer chains a parent pointer.

`schedules/fixtures/compare/live.sql` is a raw dump from before this drop, and it also has no `group_id`. Regenerate it with `dump_compare_db` before `compare_objectives --dump`. The default test suite does not load that file.
