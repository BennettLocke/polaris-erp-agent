"""Native database client smoke tests."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.engine.native_db import get_native_db_client


def test_native_db_client_init():
    client = get_native_db_client()
    assert client.db_config.get("name") == "sjagent_core"
