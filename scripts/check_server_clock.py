#!/usr/bin/env python3
import json
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def main() -> None:
    server_utc = datetime.utcnow()
    print(f"Server utcnow: {server_utc.isoformat()}")

    try:
        with urllib.request.urlopen(
            "https://worldtimeapi.org/api/timezone/Europe/Moscow", timeout=10
        ) as resp:
            data = json.load(resp)
        api_dt = datetime.fromisoformat(data["datetime"].split(".")[0])
        api_utc = api_dt.hour * 3600 + api_dt.minute * 60 + api_dt.second
        # worldtimeapi returns local MSK in datetime field
        msk_from_api = data["datetime"]
        print(f"API Europe/Moscow: {msk_from_api}")
        server_msk = server_utc.replace(
            hour=(server_utc.hour + 3) % 24
        )  # rough
        print(f"Server MSK (~utc+3): {(server_utc.hour + 3) % 24:02d}:{server_utc.minute:02d}:{server_utc.second:02d}")
    except Exception as e:
        print(f"API time check failed: {e}")


if __name__ == "__main__":
    main()
