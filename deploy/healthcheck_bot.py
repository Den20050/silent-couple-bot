"""Container healthcheck for the bot: verify the Telegram API is reachable.

Respects TELEGRAM_PROXY_URL so servers behind a proxy check the same path
the bot itself uses. Any HTTP response (including 404) means connectivity;
only network-level failures mark the container unhealthy.
"""

from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request


def main() -> int:
    handlers = []
    proxy = os.environ.get("TELEGRAM_PROXY_URL")
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    opener = urllib.request.build_opener(*handlers)
    try:
        opener.open("https://api.telegram.org/", timeout=10)
    except urllib.error.HTTPError:
        return 0  # got an HTTP response — connectivity is fine
    except Exception:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
