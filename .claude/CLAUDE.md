# Service Scheduler

Django app using ILP (PuLP/CBC) for fair volunteer scheduling.

Read **CONTEXT.md** first (project root). Features: docs/features/. Then README.md Models.

## Key Files
- Scheduling algorithm: schedules/services/scheduler.py
- Models: schedules/models.py
- Views: schedules/views.py
- Frontend JS: schedules/static/schedules/schedule.js

## Commands
- Tests: `source venv/bin/activate && python manage.py test`
- Run server: `source venv/bin/activate && python manage.py runserver`

## Conventions
- CONTEXT.md is the AI source of truth (domain, objective, constraints, UI, commands).
- Database schema: propose in README.md Models / feature spec, wait for user approval, then migrate. Test data must be tagged and cleanable. See CONTEXT.md Database.
