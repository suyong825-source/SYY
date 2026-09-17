"""출력 포매팅 헬퍼."""

from __future__ import annotations


def human_bytes(num: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(num) < 1024 or unit == "TB":
            return f"{num:,.1f} {unit}" if unit != "B" else f"{int(num)} B"
        num /= 1024
    return f"{num:.1f} TB"


def bar(ratio: float, width: int = 24) -> str:
    ratio = max(0.0, min(1.0, ratio))
    filled = int(round(ratio * width))
    return "[" + "#" * filled + "." * (width - filled) + "]"


def table(rows: list[tuple[str, ...]], headers: tuple[str, ...]) -> str:
    all_rows = [headers] + [tuple(str(c) for c in r) for r in rows]
    widths = [max(len(r[i]) for r in all_rows) for i in range(len(headers))]
    lines = [
        "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers)),
        "  ".join("-" * w for w in widths),
    ]
    for row in all_rows[1:]:
        lines.append("  ".join(c.ljust(widths[i]) for i, c in enumerate(row)))
    return "\n".join(lines)
