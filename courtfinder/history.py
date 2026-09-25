"""접수 공고 관찰 기록.

매번 수집할 때마다 '처음 본 접수 건'만 한 줄씩 덧붙인다. 이 기록이 쌓이면
코트별 개방 패턴(며칠에, 몇 시에 여는지)을 추론할 수 있고, 그때부터는
서버를 계속 두드리지 않아도 다음 회차 시각을 예측할 수 있다.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

DEFAULT_PATH = Path("history.jsonl")

FIELDS = (
    "svc_id", "place", "area", "title", "status",
    "rcpt_open_at", "rcpt_close_at", "use_start", "use_end",
)


def load(path: Path = DEFAULT_PATH) -> list[dict]:
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # 손상된 줄은 건너뛴다 — 기록 전체를 잃지 않도록
    return records


def known_ids(path: Path = DEFAULT_PATH) -> set[str]:
    return {r.get("svc_id", "") for r in load(path)}


def observe(services: list[dict], path: Path = DEFAULT_PATH,
            now: dt.datetime | None = None) -> list[dict]:
    """아직 기록에 없는 접수 건만 추가하고, 새로 추가된 것들을 돌려준다."""
    seen = known_ids(path)
    stamp = (now or dt.datetime.now(dt.timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")

    fresh = []
    for service in services:
        svc_id = service.get("svc_id")
        if not svc_id or svc_id in seen:
            continue
        record = {key: service.get(key, "") for key in FIELDS}
        record["first_seen"] = stamp
        fresh.append(record)
        seen.add(svc_id)

    if fresh:
        with path.open("a", encoding="utf-8") as handle:
            for record in fresh:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    return fresh
