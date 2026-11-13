"""Read the NDJSON user stream line by line as it arrives.

Start the server first:

    uv run python -m uvicorn config.asgi:application --reload --lifespan off

Then run:

    uv run python examples/stream_client.py           # all users
    uv run python examples/stream_client.py Tampa     # only users from Tampa
    STREAM_URL=http://127.0.0.1:8011/api/users/stream/ uv run python examples/stream_client.py

Lines arrive one by one only under ASGI (uvicorn). Under WSGI (manage.py runserver)
Django buffers the whole stream first, so every line arrives at once at the end.
"""

import json
import os
import sys
import time

import httpx

URL = os.environ.get("STREAM_URL", "http://127.0.0.1:8000/api/users/stream/")


def main() -> None:
    params = {"city": sys.argv[1]} if len(sys.argv) > 1 else None
    started = time.monotonic()

    try:
        # httpx.stream() does not read the body up front, unlike httpx.get().
        with httpx.stream("GET", URL, params=params, timeout=30) as response:
            response.raise_for_status()
            print(f"{response.status_code} {response.headers['content-type']}")

            count = 0
            # iter_lines() yields each line as soon as its "\n" arrives, joining
            # lines that were split across network chunks.
            for line in response.iter_lines():
                if not line:
                    continue
                user = json.loads(line)  # every line is a complete JSON object
                count += 1
                elapsed = time.monotonic() - started
                print(f"{elapsed:6.2f}s  #{user['id']:<3} {user['username']:<10} "
                      f"{user['profile']['city']}")
    except httpx.ConnectError:
        sys.exit(f"Cannot connect to {URL}: is the server running?")

    print(f"Done: {count} users in {time.monotonic() - started:.2f}s")


if __name__ == "__main__":
    main()
