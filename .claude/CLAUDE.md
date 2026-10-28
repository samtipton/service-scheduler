# Service Scheduler

Django app using ILP (PuLP/CBC) for fair volunteer scheduling.

Read **CONTEXT.md** first (project root). Features: docs/features/. Then SCHEMA.md, AUDIT.md, ROADMAP.md.

## Key Files
- Scheduling algorithm: schedules/services/scheduler.py
- Models: schedules/models.py
- Views: schedules/views.py
- Frontend JS: schedules/static/schedules/schedule.js

## Commands
- Tests: `source venv/bin/activate && python manage.py test`
- Run server: `source venv/bin/activate && python manage.py runserver`

## Conventions
- CONTEXT.md is the AI source of truth. SUMMARY.md is a longer older breakdown and may drift.
- Database schema: propose in SCHEMA.md / feature spec, wait for user approval, then migrate. Test data must be tagged and cleanable. See CONTEXT.md Database.
