import sys
import httpx
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
        print('Error:', detail, file=sys.stderr)
        return {"error": "api_unavailable", "detail": detail}
    if response.is_error:
        print('Error:', response.status_code, response.text, file=sys.stderr)
        return {"error": response.status_code, "detail": response.text}
    return response.json() if response.content else {"status": "ok"}


@mcp.tool()
def get_user(user_id: int) -> dict:
    """Get one user with their profile by numeric id."""
    return call_api("GET", f"/users/{user_id}/")


if __name__ == "__main__":
    mcp.run()