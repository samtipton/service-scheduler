# Who gets the leftover jobs

Open. FairJobs is per-task. The discomfort is about *totals* and *order*: 1-task men should get their share of that task first, without being stacked on it, and men who can do many tasks should fill what is left.

## What FairJobs does today

For each (person, task), CBC minimizes |end_count − fair share| over 12 months plus this month. Preference is used once. Per-task spread already caps a 1-task man: at most one if people > slots, else at most about `⌈slots/people⌉`. Cap 7 is a hard total.

Fair share of a task does not know how many *other* tasks that person can do. Sign up for six tasks at `p = 1` and you are owed six shares. Generalists land more jobs in absolute terms. The tiny `load_weight` term aims at that same high total. That is the part that feels like over-assigning the flexible men, and like 1-task men wait in line behind them.

## The feeling to preserve

1-task men get assigned first on their task, up to that task’s fair share — not beyond it. Leftover holes on that task go to higher-eligibility men, and *those* leftovers are what FairJobs should share fairly. 1-task men still must not be stacked (two Lord’s supper aids in one month when eight men want four slots).

## Approach A — load spread

Penalize spread of `jobs this month / this_month_fair_load`.

Generalists have a high fair load, so a ratio of 1.0 still means more absolute jobs. Tightening those ratios keeps FairJobs’ “six signups, six shares” shape. It does not put 1-task men first. Compressing *raw* max − min of job counts would pull a song leader and a 6-task man toward the same total and fight per-task rotation.

Fits FairJobs as another soft L1. Easy to shoehorn. Aims at the wrong target if the goal is order (specialists first) rather than equal ratios.

## Approach B — inclusion (first jobs first)

Cover as many eligible people as possible this month. Cost of a 2nd, 3rd, … job rises, so sitting-out person B’s first job beats loaded person A’s next one. Generalists are leftover stock.

Puts bodies in seats. Does not by itself protect 1-task men from being the ones who get stacked on a crowded role, and does not by itself rotate a small pool (song). Presence has to sit *under* per-task spread and FairJobs on scarce skills, or it fights them.

Fits FairJobs only as a lexicographic extra: presence first, then |end_count − fair share|. Not a tweak to `load_weight`.

## Contrast

| | A load spread | B inclusion |
|---|---|---|
| Asks | How even are load *ratios*? | How many people got at least one job? |
| 1-task man | At ratio 1.0 after his one share; no priority in line | Likely to get a first job; may still be the one stacked on a crowded task |
| Generalist | Still supposed to take ~fair_load jobs | Used after others have a first job |
| Per-task “don’t stack” | Unchanged (existing spread + L1) | Must stay a hard rule or presence will dump leftovers on 1-task men |
| Shoehorn into FairJobs | Yes (`load_weight` / extra L1) | No — different axis |

Neither is exactly “1-task men first up to fair share, then FairJobs among the rest.”

That third shape is **priority within each task**: on task *t*, fill from low-eligibility people until they hit their FairJobs target for *t*, then share remaining holes of *t* among higher-eligibility people with the same L1. Per-task spread still caps everyone. Example: four Lord’s supper slots, two 1-task aids and ten generalists → both 1-task aids get one, two leftover slots FairJobs among generalists. Four slots, six 1-task aids → four of those six get one, generalists get none, nobody gets two.

That fights “fair share of every signed-up task” for generalists (they only get what 1-task men did not take). It keeps 1-task men from being over-assigned. It is closer to the feeling than A or B alone.

## Crowded 1-task roles

A lot of 1-task men are on Lord’s supper and prayer. Song leader and similar small pools stay mixed.

If 1-task men go first on each task (inclusion, or priority within a task), those crowded roles fill from that cluster. Four table slots and six 1-task aids means four of those six get the month and the generalists who also signed up for table get none. The same pattern hits opening and closing prayer.

Over months the roster splits. Lord’s supper and prayer become the 1-task men’s jobs. Men who can do many things are pushed onto whatever is left (usher, security, song, lesson) and fall behind on table and prayer even though they are eligible. FairJobs today avoids that split because each task still owes the generalist a share.

Inclusion has the same push: a 1-task aid’s only way to get a first job is a table hole, so the solver spends table slots on those men. A generalist who already has a song slot does not “need” table for presence, so he is the one who loses it.

Per-task spread still stops stacking a 1-task man with two table Sundays. It does not keep generalists in the rotation once the 1-task cluster can fill the month.

## How it might fit FairJobs

Keep the existing per-task L1 and per-task spread. Those already stop a 1-task man from being stacked on his only role.

When two people are both still under their fair share of a task, prefer the one who is eligible for fewer tasks. That is the “assigned first” part. A soft version adds extra cost if the solver gives the hole to a high-eligibility man while a low-eligibility man is still under target on that task. A hard version fills the 1-task shares first, then runs FairJobs only on the holes that remain.

The current `load_weight` term and inclusion (approach B) do not encode that combination: under target on this task, and this is almost the only task they can do.

## Open

If leftover holes go to generalists, it is unclear whether those leftovers should still use the 12-month FairJobs window or only this month’s remaining slots. It is unclear whether “how many tasks can this person do” means every task they signed up for, or only tasks that have a hole this month. Small pools such as song and prayer already rotate inside the pool at `p = 1`; it is unclear whether they should ignore this priority.

Leave this file until that rule can be said in ordinary sentences without the shorthand.
