#!/usr/bin/env python3
"""Pull IELTS Writing exam recalls from the IELTS Buddy public Agent API.

Writes:
    writing-output/data/writing-recalls.json   full records (for provenance)
    writing-output/content/stats.json          headline numbers + topic counts

The recall endpoint is public (no token needed). If a token happens to exist at
~/.config/ielts-buddy/agent-token it is sent anyway, which is harmless.

Usage:
    python -X utf8 scripts/fetch_writing_recalls.py
    python -X utf8 scripts/fetch_writing_recalls.py --max-records 600
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ielts_buddy_api as api  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "writing-output" / "data" / "writing-recalls.json"
STATS = ROOT / "writing-output" / "content" / "stats.json"
PAGE_SIZE = 12


def pull(subject: str, max_records: int) -> list[dict]:
    token = api.load_token()
    items: list[dict] = []
    seen: set[int] = set()
    offset = 0
    while offset < max_records:
        payload = {
            "reportIds": [],
            "kind": "exam_report",
            "limit": PAGE_SIZE,
            "offset": offset,
            "query": "",
            "source": "",
            "subject": subject,
            "testDate": "",
            "testMonth": "",
        }
        resp = api.request(api.DEFAULT_BASE_URL, "/capabilities/ielts_prediction_search_hits", token, payload)
        data = resp.get("data") or {}
        batch = data.get("items") or []
        for item in batch:
            if item["id"] not in seen:
                seen.add(item["id"])
                items.append(item)
        if not batch or not data.get("hasMore"):
            break
        offset = data.get("nextOffset") or (offset + PAGE_SIZE)
    items.sort(key=lambda i: i["id"], reverse=True)
    return items


def build_stats(items: list[dict]) -> dict:
    t1: Counter[str] = Counter()
    t2: Counter[str] = Counter()
    days: set[str] = set()
    modes: Counter[str] = Counter()
    for item in items:
        days.add(item["displayDate"])
        modes[item.get("examMode") or "unknown"] += 1
        for cand in item.get("candidates") or []:
            title = (cand.get("title") or "").strip()
            if not title:
                continue
            details = cand.get("details") or ""
            if "Part 2" in details:
                t2[title] += 1
            elif "Part 1" in details:
                t1[title] += 1
    return {
        "records": len(items),
        "recallRecords": sum(1 for i in items if i.get("recallContent")),
        "examDays": len(days),
        "firstDate": min(days) if days else "",
        "lastDate": max(days) if days else "",
        "t1Topics": len(t1),
        "t2Topics": len(t2),
        "modes": dict(modes),
        "topT1": [[k, v] for k, v in t1.most_common(20)],
        "topT2": [[k, v] for k, v in t2.most_common(20)],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch IELTS writing exam recalls.")
    parser.add_argument("--subject", default="writing")
    parser.add_argument("--max-records", type=int, default=4000)
    parser.add_argument("--skip-data", action="store_true", help="only refresh stats.json")
    args = parser.parse_args(argv)

    items = pull(args.subject, args.max_records)
    if not items:
        print("没有取到任何记录，检查网络或接口。", file=sys.stderr)
        return 1

    stats = build_stats(items)
    STATS.parent.mkdir(parents=True, exist_ok=True)
    STATS.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"stats -> {STATS}  ({stats['records']} 条 / {stats['examDays']} 个考试日)")

    if not args.skip_data:
        DATA.parent.mkdir(parents=True, exist_ok=True)
        slim = [
            {
                "id": i["id"],
                "date": i["displayDate"],
                "venue": i.get("venue") or "",
                "mode": i.get("examMode") or "",
                "source": (i.get("source") or {}).get("name") or "",
                "recallContent": i.get("recallContent") or "",
                "candidates": [
                    {
                        "title": c.get("title") or "",
                        "details": c.get("details") or "",
                        "practiceUrl": c.get("practiceUrl") or "",
                    }
                    for c in (i.get("candidates") or [])
                ],
            }
            for i in items
        ]
        slim.sort(key=lambda r: (r["date"], r["id"]), reverse=True)
        DATA.write_text(json.dumps(
            {"subject": args.subject, "count": len(slim), "records": slim},
            ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"data  -> {DATA}  ({len(slim)} 条)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
