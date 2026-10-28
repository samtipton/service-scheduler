# Features

Build in this order. Current product: CONTEXT.md.

1. [scheduler-cleanup.md](scheduler-cleanup.md) — simplify the solver so experiments are cheap
2. [pluggable-objective.md](pluggable-objective.md) — swap fairness math without touching constraints
3. [resulting-count-objective.md](resulting-count-objective.md) — first new objective: L1 on resulting job counts
4. [year-sandbox.md](year-sandbox.md) — 12-month runs isolated from official schedules
5. [objective-experiment-ui.md](objective-experiment-ui.md) — Experiments page + headless year e2e (KPI matrix vs constraints)
6. [accounts.md](accounts.md) — login + congregation as the isolation boundary (sandbox vs production)

Keep each of these files the spec for that slice. Do not implement later slices on the current stats/user mash.
