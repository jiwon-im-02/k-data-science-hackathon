"""Small JSON state store for confirmed dispatches."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from config import STATE_FILE


class DispatchStateStore:
    def __init__(self, path: Path = STATE_FILE):
        self.path = path
        self._lock = threading.RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write({"commits": []})

    def _write(self, data: dict[str, Any]) -> None:
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)

    def read(self) -> dict[str, Any]:
        with self._lock:
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except (FileNotFoundError, json.JSONDecodeError):
                return {"commits": []}

    def commits(self) -> list[dict[str, Any]]:
        return list(self.read().get("commits", []))

    def add_commit(self, commit: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            data = self.read()
            commits = data.setdefault("commits", [])
            if any(item.get("order_id") == commit.get("order_id") for item in commits):
                raise ValueError("이미 배차가 확정된 주문입니다.")
            commits.append(commit)
            self._write(data)
        return commit

    def clear(self) -> None:
        with self._lock:
            self._write({"commits": []})

