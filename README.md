# dj-mcp

Django REST API for users with a nested profile, plus an [MCP](https://modelcontextprotocol.io)
server that lets AI assistants such as Claude work with those users.
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

## MCP server

`mcp_server/server.py` is a [Model Context Protocol](https://modelcontextprotocol.io) server
named `dj-users`. It lets an MCP client (Claude Code, Claude Desktop, MCP Inspector) read and
change users in plain language, for example "find everyone from Tampa" or "move user 3 to Miami".

### How it works

```
MCP client  ──stdio──▶  mcp_server/server.py  ──HTTP──▶  Django API (127.0.0.1:8000/api/)  ──▶  SQLite
```

- The client starts the server as a subprocess and talks to it over **stdio** (the default
  transport of `mcp.run()`).
- The server does not touch the database or import Django. Every tool is a thin wrapper that
  sends an HTTP request to the REST API with `httpx`, so all validation, the profile signal and
  the write logging in `UserViewSet` apply exactly as they do for `curl`.
- **The Django dev server must be running** (`uv run python manage.py runserver`). The API URL is
  set by `API_URL` at the top of `server.py`.
- Errors are returned to the model as data instead of raising, so it can see what went wrong and
  react:
  - `{"error": "api_unavailable", "detail": "ConnectError: ..."}` when the API cannot be reached;
  - `{"error": 400, "detail": "<response body>"}` for HTTP errors such as validation failures or 404.

  The same details are printed to stderr, since stdout is reserved for the MCP protocol.

### Tools

| Tool          | REST call                   | Notes                                                        |
| ------------- | --------------------------- | ------------------------------------------------------------ |
| `list_users`  | `GET /api/users/`           | Optional `city` (full name, case-insensitive), `search`, `page` |
| `get_user`    | `GET /api/users/{id}/`      | One user with profile                                        |
| `create_user` | `POST /api/users/`          | `username` required; names, email and profile fields optional |
| `update_user` | `PATCH /api/users/{id}/`    | Only the fields passed are changed                           |
| `delete_user` | `DELETE /api/users/{id}/`   | Marked `destructive_hint`, so clients ask for confirmation   |

Profile fields (`birth_date` as `YYYY-MM-DD`, `city`, `workplace`) are flat tool arguments; the
server nests them into `profile` before calling the API.

### Resources and prompts

Resources are read-only data that the user or the client attaches to the conversation as context;
unlike tools, the model does not call them to act. Both return JSON:

- **Static resource** `users://cities` counts users per city across all pages of the API, for
  example `{"total_users": 11, "cities": {"Miami": 2, "Tampa": 1, ...}}`. It has a fixed URI, so
  clients list it directly; in Claude Code type `@dj-users:users://cities` in the prompt.
- **Resource template** `users://{user_id}` returns the same data as `get_user`. The user fills in
  the id, e.g. `users://3`.
- **Prompt** `city_report(city)` produces the request "List the users from {city} and summarize
  where they work.", which the model answers with `list_users`.

### Connecting a client

Start the API first:

```bash
uv run python manage.py runserver
```

**Claude Code** — register the server for this project:

```bash
claude mcp add dj-users -- uv run --directory /path/to/dj_mcp python mcp_server/server.py
```

or create `.mcp.json` in the project root (it is git-ignored, because the path is machine-specific):

```json
{
  "mcpServers": {
    "dj-users": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "--directory", "/path/to/dj_mcp", "python", "mcp_server/server.py"]
    }
  }
}
```

Claude Desktop uses the same `mcpServers` block in its `claude_desktop_config.json`.

**MCP Inspector** — try the tools in a browser without an AI client:

```bash
npx @modelcontextprotocol/inspector uv run python mcp_server/server.py
```

`--directory` makes uv use this project's environment and Python no matter which directory the
client starts the server from.

## Permissions

The API is open (`AllowAny`) for development. To lock it down, change
`DEFAULT_PERMISSION_CLASSES` in `REST_FRAMEWORK` in `config/settings.py`.
