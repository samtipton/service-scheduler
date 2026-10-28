# Year sandbox

Isolation for 12-month solver runs. UI, KPIs, and cleanup: [objective-experiment-ui.md](objective-experiment-ui.md).

A run copies people, `TaskPreference`s, and optional production `Assignment` history at click time. Sequential generate: month 1’s assignments are history for month 2. Objective name from [pluggable-objective.md](pluggable-objective.md).

`Schedule.kind=experiment` plus `experiment_id`. `is_official` is false. Experiment `Assignment`s must not appear in production `MonthView` or in a production solver window. Until [accounts.md](accounts.md), that filter is the wall.

## Done when

A run can persist 12 months that `MonthListView` does not list. Deleting the run removes only those rows.
