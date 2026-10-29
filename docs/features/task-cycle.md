# TaskCycle

An ordered list of people who own a task and take consecutive occurrences in that order, wrapping forever. Two members is A-B-A-B. Three is A-B-C-A.

Today, two active elders on Sunday 10:30 announcements already get that pattern from consecutive-week: the same man cannot take two neighboring occurrences, there is one hole per Sunday, so they flip. A third *active* elder breaks that. Consecutive-week only forbids back-to-back; FairJobs then shares the slot among three. TaskCycle is the rule for “these people, in this order,” including a third elder.

## Data

`TaskCycleMember(task, user, order)`. Inline on Task. Empty means current behavior (anyone with `p > 0` may take the task; consecutive-week still applies).

Two or more members: only those people get the task, even if someone else has `p > 0`. Consecutive occurrences of that task, including the last hole of the previous month (calendar Assignments, or `base_schedule` until that is removed), follow the list:

```
x[member i on t_j]  ≤  x[member i+1 on t_{j+1}]
```

With fill-every-hole that is a strict handoff. The previous occurrence’s assignee picks who is due next.

Do not reuse `rotation_group` (that is a FairJobs family across different tasks). Do not infer a cycle from “eligible pool size 2.”

## Conflicts

If the man who is due is blocked that week (exclusion, cap 7, `TaskRequires`), the hole has no legal cycle member. Same wall as two-person consecutive-week today. Cycle does not invent a fourth person. Leave the month infeasible or unfilled rather than silently skipping ahead in the list, unless a later spec says otherwise.

## Out of scope

Using a cycle on song, prayer, or Lord’s supper. Soft / FairJobs-weighted cycles. Auto-building a cycle from whoever has `p > 0`.

## Done when

Admin can put three elders on announcements in order. After elder 1’s last Sunday of May, June starts on elder 2, then 3, then 1. A fourth man with `p > 0` does not get the slot. Two-elder months without a cycle still alternate via consecutive-week.
