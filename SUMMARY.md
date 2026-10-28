## Service Scheduler - Codebase Breakdown

### Overview

This is a **Django-based volunteer/church service scheduling application** that uses **integer linear programming (ILP)** to automatically generate fair monthly schedules. It assigns people to recurring service tasks (e.g., song leader, preacher, cantor) while respecting preferences, eligibility, exclusions, and historical fairness.

**Tech Stack**: Django 5.1.7 | PostgreSQL | PuLP (CBC solver) | Vanilla JS | pdfkit

---

### Data Model

| Model | Purpose |
|---|---|
| **User** | Custom auth user (email-based login), tracks eligible tasks and assignment history |
| **Service** | A recurring event on a specific day of week (e.g., Sunday AM service) |
| **Task** | A role within a service (e.g., Song Leader), with M2M self-referential `excludes` and a `time_period` |
| **TaskPreference** | Per-user weighting (float >= 0) for each task; 0 = ineligible |
| **Schedule** | A monthly schedule; self-referential `base_schedule` FK for branching; `is_official` flag (one per month) |
| **Assignment** | Links a User to a Task on a specific date within a Schedule |
| **AssignmentStats** | Tracks `ideal_average`, `actual_average`, and `assignment_delta` per user/task/schedule for fairness |

Stats are automatically maintained via Django `post_save` signals on Assignment.

---

### Core Scheduling Algorithm (`schedules/services/scheduler.py`)

The scheduler formulates the problem as an **Integer Linear Program** solved by the CBC solver via PuLP.

#### Variables

Binary variables `x[(date_task, user)]` for every eligible (date, task, user) combination. A value of 1 means the user is assigned; 0 means not.

#### Objective Function - Maximize Fairness

Canonical definition: **CONTEXT.md** (Objective).

```
maximize: Σ [ideal_avg(u, t) × preference(u, t) - adjusted_actual_avg(u, t)] × x[(dt, u)]
```

`ideal` is already `pref / Σ pref`. Multiplying by `pref` again is the personal target modifier — `0.5` halves the target, `1.5` raises it 50%. Under target → assign; over target → avoid.

#### Jitter for New Volunteers

Users with very few historical assignments (below 5% of their ideal) get an **adjusted actual average** pulled toward their ideal by a random factor (0.9–1.1×). This prevents the algorithm from deterministically flooding new volunteers with assignments and provides natural variety as a tiebreaker.

#### Constraints

| # | Constraint | Effect |
|---|---|---|
| 1 | **Past Assignments** | All base schedule (previous month) assignments are locked: `x == 1` |
| 2 | **One Person Per Task** | Exactly one person assigned per date-task: `Σ x == 1` |
| 3 | **Eligible Only** | Enforced structurally — only eligible pairs have variables |
| 4 | **Task Exclusions** | Mutually-excluding tasks (e.g., Preacher + Cantor) cannot be assigned to the same person in the same week: `x[dt1,u] + x[dt2,u] <= 1` |
| 5 | **Fair Distribution Per Task** | If more eligible people than slots: each person gets at most 1. Otherwise: each gets between 1 and `⌈slots/people⌉` |
| 6 | **Month Boundary** | Prevents same person from having the same task in consecutive weeks, including across the month boundary (checks base schedule for last week of prior month) |
| 7 | **Total Cap** | Max 7 total assignments per person per month |
| 8 | **Locked-In Assignments** | User-specified pre-assignments are forced: `x == 1`. These bypass fairness and consecutive-week constraints |

#### Solve Flow

1. **Init**: Load users, services, tasks, eligibility, base schedule stats, preferences, and locked-in assignments
2. **Build**: Create ~1,000–2,000 binary variables, set objective function, add ~400–500 constraints
3. **Solve**: CBC branch-and-bound (typically 2–5 seconds)
4. **Extract**: Read solution values, validate eligibility, return `OrderedDict` of `"YYYY-MM-DD-task_id" → "Last, First"`

---

### User Experience Features

#### Schedule List & Creation
- Lists all schedules ordered by date (newest first)
- Modal dialog to create a new schedule with name, description, date, and optional **base schedule** (branching — like git for schedules)
- One schedule per month can be marked **official** via admin

#### Monthly Schedule View
- Full-month table: services arranged as horizontal/vertical sections, dates as columns, tasks as rows
- Each cell is an **editable input** for assigning a person to a task on a date

#### Assignment Input with Autocomplete
- Each input is backed by an HTML5 `<datalist>` populated with eligible users for that task
- Users are sorted by `assignment_delta` (least-assigned shown first for fairness visibility)
- Typing filters the list; pressing Enter auto-completes the first match

#### Drag-and-Drop
- Native HTML5 DnD on assignment cells
- Drag opacity drops to 0.4; drop target gets a dotted border
- Dropping **swaps** the two cells' contents
- Automatically triggers save after swap

#### Auto-Save with Dirty Tracking
- On focus: stores original value and clears field for editing
- On change: sets a `dirty` flag
- On blur: if dirty, triggers a **debounced save** (2-second delay, resets on further edits)
- Only **changed assignments** (delta from last known state) are sent to the backend via PUT
- Deletions sent as `null` values

#### Auto-Generate Button
- Shows **skeleton shimmer animations** in empty cells while the solver runs
- POSTs all current (non-empty) assignments as locked-in constraints
- Solver returns the full optimized schedule; UI populates all cells
- Users can then manually adjust and re-generate iteratively

#### Assignment Frequency Panel
- Toggleable side panel showing each person's assignment count
- Sorted by count (descending), then alphabetically
- **Hover highlighting**: mousing over a name highlights all their assignments across the table in sky blue

#### Toast Notifications
- Bottom-center non-blocking messages: "Saving...", "Saved", "Done.", "Error loading assignments"
- Auto-dismiss after 1 second with opacity transition

#### PDF Export
- One-click download renders the schedule as a **Legal landscape PDF** via pdfkit
- Embeds all CSS inline; same table layout as the web view
- Filename: `schedule-{month}-{year}.pdf`

#### Clear Schedule
- Confirmation dialog before wiping all assignments
- DELETE request removes all assignments; UI clears all inputs

#### Floating Toolbar
- Fixed-position button group (Generate, PDF, Toggle Count, Clear)
- Hidden at `opacity: 0`, appears on hover at `opacity: 0.85` — stays out of the way

#### Double-Click to Clear
- Double-clicking a cell clears both its value and placeholder, immediately triggering a save

---

### Authentication & Security
- Custom `LoginRequiredMiddleware` redirects unauthenticated `/schedules/` requests to `/login/`
- Standard Django CSRF protection on all mutating endpoints
- PDF generation disables external links for security
