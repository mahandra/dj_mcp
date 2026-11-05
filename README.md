# dj-mcp

Django REST API for users with a nested profile.
Built with Django 6.1, Django REST Framework, SQLite and [uv](https://docs.astral.sh/uv/).

## Setup

```bash
uv sync
uv run python manage.py migrate
uv run python manage.py seed_users   # optional: 10 demo users, safe to re-run
```

The project uses a uv-managed Python 3.12 (`python-preference = "only-managed"` in
`pyproject.toml`) because Django 6.1 needs SQLite 3.37+, which some system Python builds
do not ship. `uv sync` downloads it automatically.

## Running

```bash
uv run python manage.py runserver         # http://127.0.0.1:8000/api/
uv run python manage.py test              # run the test suite
uv run python manage.py createsuperuser   # for the admin at /admin/
```

## API

| Method        | URL                       | Description                          |
| ------------- | ------------------------- | ------------------------------------ |
| `GET`         | `/api/users/`             | List users (10 per page, `?page=N`)  |
| `GET`         | `/api/users/{id}/`        | Single user with profile             |
| `POST`        | `/api/users/`             | Create a user                        |
| `PUT`/`PATCH` | `/api/users/{id}/`        | Update a user                        |
| `DELETE`      | `/api/users/{id}/`        | Delete a user and their profile      |
| `GET`         | `/api/users/?city=Tampa`  | Filter by city (case-insensitive)    |
| `GET`         | `/api/users/?search=text` | Search username, names and workplace |

User representation:

```json
{
  "id": 1,
  "username": "alice",
  "first_name": "Alice",
  "last_name": "Morgan",
  "email": "alice@example.com",
  "profile": {
    "birth_date": "1990-03-14",
    "city": "Tampa",
    "workplace": "Bayshore Software"
  }
}
```

`profile` and all its fields are optional in requests. Profile fields left out of a
request keep their current values, on `PUT` as well as `PATCH`.

Passwords are not part of the API: users created through it have an unusable password
and cannot log in.

### curl examples

```bash
# List
curl http://127.0.0.1:8000/api/users/
curl "http://127.0.0.1:8000/api/users/?page=2"

# Retrieve
curl http://127.0.0.1:8000/api/users/1/

# Create
curl -X POST http://127.0.0.1:8000/api/users/ \
  -H "Content-Type: application/json" \
  -d '{"username": "zoe", "first_name": "Zoe", "last_name": "Adams",
       "email": "zoe@example.com",
       "profile": {"birth_date": "1992-04-18", "city": "Tampa", "workplace": "Acme"}}'

# Full update
curl -X PUT http://127.0.0.1:8000/api/users/11/ \
  -H "Content-Type: application/json" \
  -d '{"username": "zoe", "first_name": "Zoe", "last_name": "Baker",
       "email": "zoe@example.com",
       "profile": {"birth_date": "1992-04-18", "city": "Miami", "workplace": "Globex"}}'

# Partial update
curl -X PATCH http://127.0.0.1:8000/api/users/11/ \
  -H "Content-Type: application/json" \
  -d '{"profile": {"city": "Orlando"}}'

# Delete
curl -X DELETE http://127.0.0.1:8000/api/users/11/

# Filter by city
curl "http://127.0.0.1:8000/api/users/?city=Tampa"

# Search
curl "http://127.0.0.1:8000/api/users/?search=rossi"
```

## Permissions

The API is open (`AllowAny`) for development. To lock it down, change
`DEFAULT_PERMISSION_CLASSES` in `REST_FRAMEWORK` in `config/settings.py`.
