# Audit

Docs vs code vs stated requirements. Source of truth for AI: CONTEXT.md.

## Requirements gaps
- Preference is `≥ 0` with no upper bound (`0` ineligible, `1` baseline, `>1` want more).
- Exclusions: “same day or same service.” Solver uses week-aligned pairs, including weekly vs daily padding.
- New members over-scheduled. Jitter only if actual &lt; 5% of target. `at least once` when slots ≥ eligible people. Lifetime share of 0 looks infinitely behind.
- Charts (counts, per-task, per-month) need Assignment rows; AssignmentStats does not serve that.
- Multi-church / multiple managers: not modeled. TODOs say “group.”

## Logic
- Preference is applied twice: `ideal = p/Σp` (`calculate_ideal_average`), then `* p` again in `set_objective_function` (ac85a7e). `p` does not cancel (`p²/Σp − actual`). Extra multiply was meant as a modifier; it squares weights already in `ideal`.
- Fairness is lifetime share of all assignments for a task, not a window or count deficit.
- Cap 7, consecutive-week skip, and “fill every slot” are hardcoded.
- Locked cells skip consecutive-week and per-task caps.
- Past-month assignments are extra ILP variables.

## Database
- `AssignmentStats` M2M snapshots + signals + bulk regen is the bulk of stored derived data.
- `User` is both volunteer and login.
- `Task.time_period` duplicates `Service.day_of_week`.
- `Assignment.assigned_at` is DateTime; no uniqueness.
- `core` app is seed-only. Root `settings.py` is leftover. Deleted commands remain as `.pyc`.

## Docs / AI
- README is install-only. SUMMARY.md is useful but drifts (preference, jitter, stats).
- Scheduler tests are mocks; they do not solve a real month.
- CSRF exempt on generate/update/clear/PDF. Duplicate `get_service_day` in utils and templatetags.

## UX (kept)
Month grid, datalist, drag-swap, autosave, generate, PDF, assignment counts. Official-schedule is admin-only.
