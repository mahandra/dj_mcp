import sys
import httpx
from mcp.types import ToolAnnotations
from mcp.server import MCPServer

API_URL = "http://127.0.0.1:8000/api"
mcp = MCPServer("dj-users")


def call_api(method: str, path: str, **kwargs) -> dict:
    """Call the REST API and return errors as data the model can read."""
    try:
        response = httpx.request(method, f"{API_URL}{path}", **kwargs)
    except httpx.RequestError as exc:
        # str(exc) can be empty (e.g. timeouts), so keep the exception type.
        detail = f"{type(exc).__name__}: {exc}"
        print('Error--:', detail, file=sys.stderr)
        return {"error": "api_unavailable", "detail": detail}
    if response.is_error:
        print('Error---:', response.status_code, response.text, file=sys.stderr)
        return {"error": response.status_code, "detail": response.text}
    return response.json() if response.content else {"status": "ok"}


@mcp.tool()
def get_user(user_id: int) -> dict:
    """Get one user with their profile by numeric id."""
    return call_api("GET", f"/users/{user_id}/")

@mcp.tool()
def list_users(
    city: str | None = None,
    search: str | None = None,
    page: int = 1,
) -> dict:
    """List users, 10 per page, with optional filters.

    Args:
        city: Full city name, case-insensitive. Partial names do not match.
        search: Text to find in username, first name or last name or workspace.
        page: Page number, starting at 1. Use the "next" field to see if more exist.
    """
    params = {"page": page, "city": city, "search": search}
    params = {key: value for key, value in params.items() if value is not None}
    return call_api("GET", "/users/", params=params)

def compact(**fields) -> dict:
    """Drop arguments the caller did not pass."""
    return {key: value for key, value in fields.items() if value is not None}


@mcp.tool()
def create_user(
    username: str,
    first_name: str | None = None,
    last_name: str | None = None,
    email: str | None = None,
    birth_date: str | None = None,
    city: str | None = None,
    workplace: str | None = None,
) -> dict:
    """Create a user with an optional profile.

    Args:
        username: Unique login name.
        birth_date: Date in YYYY-MM-DD format.
    """
    body = compact(
        username=username, first_name=first_name, last_name=last_name, email=email
    )
    body["profile"] = compact(birth_date=birth_date, city=city, workplace=workplace)
    return call_api("POST", "/users/", json=body)


@mcp.tool()
def update_user(
    user_id: int,
    username: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    email: str | None = None,
    birth_date: str | None = None,
    city: str | None = None,
    workplace: str | None = None,
) -> dict:
    """Change only the given fields of a user. Omitted fields stay as they are.

    Args:
        user_id: Numeric id of the user to change.
        birth_date: Date in YYYY-MM-DD format.
    """
    body = compact(
        username=username, first_name=first_name, last_name=last_name, email=email
    )
    profile = compact(birth_date=birth_date, city=city, workplace=workplace)
    if profile:
        body["profile"] = profile
    return call_api("PATCH", f"/users/{user_id}/", json=body)


@mcp.tool(annotations=ToolAnnotations(destructive_hint=True))
def delete_user(user_id: int) -> dict:
    """Permanently delete a user and their profile. This cannot be undone."""
    return call_api("DELETE", f"/users/{user_id}/")

###### Resources ######
@mcp.resource("users://{user_id}")
def user_resource(user_id: int) -> dict:
    """User data as a readable resource."""
    return call_api("GET", f"/users/{user_id}/")


@mcp.prompt()
def city_report(city: str) -> str:
    """Build a request for a report on users in one city."""
    return f"List the users from {city} and summarize where they work."


if __name__ == "__main__":
    mcp.run()