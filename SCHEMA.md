# Schema (current)

Renders in Cursor via Markdown Preview (Mermaid is built-in; optional: “Markdown Preview Mermaid Support”).

```mermaid
erDiagram
    User ||--o{ Schedule : creates
    User ||--o{ Assignment : assigned
    User ||--o{ TaskPreference : prefers
    User ||--o{ AssignmentStats : stats
    Service ||--|{ Task : has
    Task ||--o{ Assignment : filled
    Task ||--o{ TaskPreference : preferred
    Task ||--o{ AssignmentStats : stats
    Task }o--o{ Task : excludes
    Schedule ||--o{ Assignment : contains
    Schedule }o--o{ AssignmentStats : snapshots
    Schedule }o--o| Schedule : base_schedule

    User {
        email string UK
        first_name string
        last_name string
        is_active bool
    }
    Service {
        name string
        day_of_week int "0=Sun, null=week"
        start_time time
    }
    Task {
        id string PK
        name string
        time_period string "duplicates Service"
        order int
    }
    TaskPreference {
        value float ">=0; 0 ineligible; 1 baseline; >1 want more"
    }
    Schedule {
        date date "month"
        is_official bool "TO REMOVE unused"
    }
    Assignment {
        assigned_at datetime "should be date"
    }
    AssignmentStats {
        ideal_average decimal "derived"
        actual_average decimal "derived"
        assignment_delta decimal "derived"
    }
```

**Derived / redundant:** `AssignmentStats` (recomputable from Assignment + preference). `Task.time_period` vs `Service.day_of_week`. Task self-exclusion. `Schedule.base_schedule` git-branching. No unique `(schedule, task, assigned_at)`. No `Church`. Volunteer = login User.
