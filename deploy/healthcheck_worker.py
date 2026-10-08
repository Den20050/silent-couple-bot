"""Container healthcheck for the worker: verify Redis (the arq backend) answers PING."""

from __future__ import annotations

import os
import sys

import redis


def main() -> int:
    url = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")
    try:
        client = redis.Redis.from_url(url, socket_connect_timeout=5, socket_timeout=5)
        return 0 if client.ping() else 1
    except Exception:
        return 1


if __name__ == "__main__":
    sys.exit(main())
