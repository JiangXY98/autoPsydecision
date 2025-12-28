# scripts/monthly_audit.py
from __future__ import annotations

import json
import statistics as stats
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import re

DATA_DIR = Path("data/weekly")
REPORT_DIR = Path("reports")

def parse_run_date_from_filename(p: Path) -> str:
    # expects YYYY-MM-DD.json
    m = re.match(r"(\d{4}-\d{2}-\d{2})\.json$", p.name)
    return m.group(1) if m else "unknown"

def safe_num(x):
    try:
        if x is None:
            return None
        if isinstance(x, (int, float)):
            return float(x)
        x = str(x).strip()
        if x.upper() == "N/A" or x == "":
            return None
        return float(x)
    except Exception:
        return None

def mean_or_none(vals):
    vals = [v for v in vals if v is not None]
    return round(stats.mean(vals), 2) if vals else None

def load_weekly_records():
    if not DATA_DIR.exists():
        raise SystemExit(f"Missing {DATA_DIR}. Create weekly JSON first.")

    files = sorted(DATA_DIR.glob("*.json"))
    records = []
    for f in files:
        run_date = parse_run_date_from_filename(f)
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue

        if not isinstance(data, list):
            continue

        for item in data:
            if not isinstance(item, dict):
                continue

            rec = {
                "run_date": run_date,
                "title": (item.get("title") or "").strip(),
                "journal": (item.get("journal") or "").strip(),
                "doi": (item.get("doi") or "").strip(),
                "research_score": safe_num(item.get("research_score")),
                "impact_score": safe_num(item.get("impact_score")),
                "topic_tags": item.get("topic_tags") or [],
                "method_tags": item.get("method_tags") or [],
            }
            records.append(rec)

    return records, files

def week_key(date_str: str) -> str:
    # ISO week bucket; good enough for trend plots in markdown
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        iso = dt.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"
    except Exception:
        return "unknown"

def main():
    records, files = load_weekly_records()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    # ---- Global summary ----
    rs_all = [r["research_score"] for r in records if r["research_score"] is not None]
    is_all = [r["impact_score"] for r in records if r["impact_score"] is not None]

    # ---- Journal bias table ----
    by_journal = defaultdict(list)
    for r in records:
        if r["journal"]:
            by_journal[r["journal"]].append(r)

    journal_rows = []
    global_rs = stats.mean(rs_all) if rs_all else None
    global_is = stats.mean(is_all) if is_all else None

    for j, rows in by_journal.items():
        rs = mean_or_none([x["research_score"] for x in rows])
        im = mean_or_none([x["impact_score"] for x in rows])
        n = len(rows)
        rs_delta = round(rs - global_rs, 2) if (rs is not None and global_rs is not None) else None
        im_delta = round(im - global_is, 2) if (im is not None and global_is is not None) else None
        journal_rows.append((n, j, rs, rs_delta, im, im_delta))

    journal_rows.sort(reverse=True, key=lambda x: x[0])  # by N desc

    # ---- Topic trend (last 26 weeks) ----
    # Build week -> tag -> list(scores)
    week_tag_rs = defaultdict(lambda: defaultdict(list))
    week_tag_is = defaultdict(lambda: defaultdict(list))

    for r in records:
        wk = week_key(r["run_date"])
        tags = r["topic_tags"] if isinstance(r["topic_tags"], list) else []
        for t in tags:
            week_tag_rs[wk][t].append(r["research_score"])
            week_tag_is[wk][t].append(r["impact_score"])

    all_weeks = sorted([week_key(parse_run_date_from_filename(f)) for f in files if parse_run_date_from_filename(f) != "unknown"])
    all_weeks = sorted(set(all_weeks))
    last_weeks = all_weeks[-26:] if len(all_weeks) > 26 else all_weeks

    # Aggregate overall topic stats
    by_topic = defaultdict(list)
    for r in records:
        tags = r["topic_tags"] if isinstance(r["topic_tags"], list) else []
        for t in tags:
            by_topic[t].append(r)

    topic_rows = []
    for t, rows in by_topic.items():
        rs = mean_or_none([x["research_score"] for x in rows])
        im = mean_or_none([x["impact_score"] for x in rows])
        n = len(rows)
        topic_rows.append((n, t, rs, im))
    topic_rows.sort(reverse=True, key=lambda x: x[0])

    # ---- Write report ----
    now = datetime.now().strftime("%Y-%m")
    out_path = REPORT_DIR / f"audit_{now}.md"

    lines = []
    lines.append(f"# Monthly Audit Report ({now})\n")
    lines.append(f"- Data files: {len(files)} weekly snapshots\n")
    lines.append(f"- Articles scored (rows): {len(records)}\n")
    lines.append(f"- Global mean Research Score: {round(global_rs,2) if global_rs is not None else 'N/A'}\n")
    lines.append(f"- Global mean Impact Score: {round(global_is,2) if global_is is not None else 'N/A'}\n")

    # Journal table
    lines.append("\n## Journal Summary (by volume)\n")
    lines.append("| N | Journal | Mean Research | Δ vs Global | Mean Impact | Δ vs Global |\n")
    lines.append("|---:|---|---:|---:|---:|---:|\n")
    for n, j, rs, rsd, im, imd in journal_rows[:30]:
        lines.append(f"| {n} | {j} | {rs if rs is not None else 'N/A'} | {rsd if rsd is not None else 'N/A'} | {im if im is not None else 'N/A'} | {imd if imd is not None else 'N/A'} |\n")

    # Topic table
    lines.append("\n## Topic Summary (by volume)\n")
    lines.append("| N | Topic Tag | Mean Research | Mean Impact |\n")
    lines.append("|---:|---|---:|---:|\n")
    for n, t, rs, im in topic_rows[:30]:
        lines.append(f"| {n} | {t} | {rs if rs is not None else 'N/A'} | {im if im is not None else 'N/A'} |\n")

    # Trend section (compact)
    lines.append("\n## Topic Trend (last 26 weeks, weekly means)\n")
    lines.append(f"Weeks covered: {', '.join(last_weeks) if last_weeks else 'N/A'}\n\n")
    # pick top 6 topics by volume to keep readable
    top_topics = [t for _, t, _, _ in topic_rows[:6]]
    if not top_topics or not last_weeks:
        lines.append("_Not enough data to compute trends._\n")
    else:
        lines.append("### Research Score trend\n")
        lines.append("| Week | " + " | ".join(top_topics) + " |\n")
        lines.append("|---|"+ "|".join(["---:"] * len(top_topics)) + "|\n")
        for wk in last_weeks:
            row = []
            for t in top_topics:
                m = mean_or_none(week_tag_rs[wk].get(t, []))
                row.append(str(m) if m is not None else "")
            lines.append(f"| {wk} | " + " | ".join(row) + " |\n")

        lines.append("\n### Impact Score trend\n")
        lines.append("| Week | " + " | ".join(top_topics) + " |\n")
        lines.append("|---|"+ "|".join(["---:"] * len(top_topics)) + "|\n")
        for wk in last_weeks:
            row = []
            for t in top_topics:
                m = mean_or_none(week_tag_is[wk].get(t, []))
                row.append(str(m) if m is not None else "")
            lines.append(f"| {wk} | " + " | ".join(row) + " |\n")

    out_path.write_text("".join(lines), encoding="utf-8")
    print(f"Wrote report: {out_path}")

if __name__ == "__main__":
    main()
