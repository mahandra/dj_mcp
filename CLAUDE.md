# CLAUDE.md

Django 6.1 + Django REST Framework API exposing users with a nested profile. SQLite database.

## Commands

Use uv for everything; never pip or requirements.txt.

```bash
uv sync                                      # install dependencies
uv run python manage.py migrate              # apply migrations
uv run python manage.py runserver            # dev server at http://127.0.0.1:8000/api/
uv run python manage.py test                 # all tests
uv run python manage.py test api.tests.UserApiTests.test_create_with_profile   # one test
uv run python manage.py seed_users           # idempotent demo data (10 users)
uv run python manage.py makemigrations api   # after changing api/models.py
```

## Structure

- `config/` — project package: `settings.py` (includes `REST_FRAMEWORK`), root `urls.py`.
- `api/models.py` — `Profile`, one-to-one with the built-in `User`.
- `api/signals.py` — `post_save` receiver that creates the `Profile`; connected in `api/apps.py`.
- `api/serializers.py` — `UserSerializer` with nested `ProfileSerializer` and its writes.
- `api/views.py` — `UserViewSet`: CRUD, `?city=` filter, `?search=`.
- `api/urls.py` — `DefaultRouter`, included under `/api/` by `config/urls.py`.
- `api/admin.py` — `UserAdmin` with the `Profile` inline.
- `api/management/commands/seed_users.py` — demo data.
- `api/tests.py` — all tests.

## Conventions

- **Every User has a Profile, created by the signal.** Never create a `Profile` directly in
  application code: read and update `user.profile` instead. A second insert violates the
  one-to-one constraint.
- **Nested writes live in `UserSerializer`.** They go through `user.profile` rather than
  `update_or_create`, because `UserViewSet` loads it with `select_related` and the response is
  serialized from that cached object.
- **The admin inline is hidden on the add form** because the signal has already created the
  `Profile` by the time inlines are saved.
- **All API routes live under `/api/`.** Register new viewsets on the router in `api/urls.py`.
- **Project-wide API behaviour is set in `REST_FRAMEWORK`** (permissions, pagination), not per
  view. `AllowAny` is a development default.
- **Credentials are not exposed by the API.** Do not add `password` to `UserSerializer` fields.
- `city` filtering uses a query parameter in `get_queryset`; `django-filter` is not a dependency.

## Environment

`pyproject.toml` sets `python-preference = "only-managed"`: Django 6.1 requires SQLite >= 3.37, and
pyenv/system Pythons here link an older one (`NotSupportedError: SQLite 3.37 or later is required`).
Keep this setting unless Django is downgraded.
