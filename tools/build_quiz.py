#!/usr/bin/env python3
"""Google Trends 원본(data/raw/trends_*.json) -> quiz.json

trends-checklist.md 의 표(번호, 카테고리, 검색어 A/B, 파일명)를 읽고,
tools/fetch_all.py 가 data/raw/ 에 받아 둔 원본을 찾아 기간 합계를 비교한 뒤
quiz.json 을 만든다. 원본은 읽기만 하고 고치지 않는다.

사용법:
    python tools/build_quiz.py
    python tools/build_quiz.py --min-ratio 1.2 --raw-dir data/raw --out quiz.json
"""
import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

PERIOD = "2026-01-01 ~ 2026-10-31"
REGION = "대한민국"
SOURCE = "Google Trends (웹 검색, 상대지수)"
PERIOD_START = dt.date(2026, 1, 1)   # 주 시작일이 이 날짜 이후인 주만 쓴다 (12/28~1/3 주는 제외)
PERIOD_END = dt.date(2026, 10, 31)


def parse_checklist(path):
    """체크리스트 표에서 문항 목록을 읽는다."""
    pairs = []
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 6 or not cells[1].isdigit():
            continue
        pairs.append({
            "n": int(cells[1]),
            "category": cells[2],
            "a": cells[3],
            "b": cells[4],
            "file": cells[5],
        })
    return pairs


def read_series(path):
    """Trends 원본 JSON에서 (기간 안 주의 열별 합계, 사용한 주 수)를 돌려준다."""
    text = path.read_text(encoding="utf-8")
    body = json.loads(text[text.index(chr(10)) + 1:])  # 첫 줄은 ")]}'," 머리글
    rows = body["default"]["timelineData"]
    totals = [0.0, 0.0]
    used = 0
    for r in rows:
        start = dt.datetime.fromtimestamp(int(r["time"]), dt.timezone.utc).date()
        if not (PERIOD_START <= start <= PERIOD_END):
            continue
        used += 1
        for k in range(2):
            # Trends 는 1 미만을 "<1" 로 표기한다(값은 0). 0.5 로 셈한다
            totals[k] += 0.5 if r["formattedValue"][k] == "<1" else float(r["value"][k])
    if not used:
        raise ValueError("기간 안의 주가 없습니다")
    return totals, used


def main():
    here = Path(__file__).resolve().parent.parent   # 저장소 최상위
    ap = argparse.ArgumentParser()
    ap.add_argument("--checklist", default=str(here / "trends-checklist.md"))
    ap.add_argument("--raw-dir", default=str(here / "data" / "raw"))
    ap.add_argument("--out", default=str(here / "quiz.json"))
    ap.add_argument("--min-ratio", type=float, default=1.2)
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    pairs = parse_checklist(Path(args.checklist))
    if not pairs:
        sys.exit("체크리스트에서 문항을 읽지 못했습니다.")
    raw_dir = Path(args.raw_dir)

    questions, excluded = [], []
    for p in pairs:
        f = raw_dir / ("trends_" + p["file"].removesuffix(".csv") + ".json")
        tag = f"#{p['n']:>2} {p['category']} {p['a']} vs {p['b']}"
        if not f.exists():
            excluded.append({**p, "reason": "파일 없음"})
            print(f"[누락] {tag}")
            continue
        try:
            totals, nrows = read_series(f)
        except Exception as e:
            excluded.append({**p, "reason": f"읽기 실패: {e}"})
            print(f"[오류] {tag} - {e}")
            continue
        warn = ""
        ta, tb = totals
        hi, lo = max(ta, tb), min(ta, tb)
        if hi <= 0 or lo / nrows < 1:
            excluded.append({**p, "reason": "값이 너무 작음/데이터 부족", "a_total": ta, "b_total": tb})
            print(f"[부족] {tag} - 합계 {ta:g} / {tb:g}{warn}")
            continue
        ratio = hi / lo
        if ratio < args.min_ratio:
            excluded.append({**p, "reason": f"격차 작음 ({ratio:.2f}배)", "a_total": ta, "b_total": tb})
            print(f"[격차] {tag} - {ratio:.2f}배 < {args.min_ratio}{warn}")
            continue
        answer = "a" if ta > tb else "b"
        questions.append({
            "id": f"q{p['n']:02d}",
            "category": p["category"],
            "a": p["a"],
            "b": p["b"],
            "answer": answer,
            "ratio": round(ratio, 2),
            "a_total": round(ta, 1),
            "b_total": round(tb, 1),
        })
        print(f"[ OK ] {tag} - 정답 {p[answer]} ({ratio:.2f}배){warn}")

    result = {
        "title": "어느 것이 가장 많이 검색되었을까?",
        "period": PERIOD,
        "region": REGION,
        "source": SOURCE,
        "min_ratio": args.min_ratio,
        "questions": questions,
        "excluded": excluded,
    }
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    # 요약
    print(f"\n채택 {len(questions)}문항 / 제외 {len(excluded)}문항 -> {args.out}")
    by_cat = {}
    for q in questions:
        by_cat[q["category"]] = by_cat.get(q["category"], 0) + 1
    for c in dict.fromkeys(p["category"] for p in pairs):
        n = by_cat.get(c, 0)
        print(f"  {c}: {n}/5" + ("" if n >= 5 else "  <- 교체 쌍 필요"))
    a_cnt = sum(1 for q in questions if q["answer"] == "a")
    if questions:
        print(f"정답 위치: A {a_cnt}개 / B {len(questions) - a_cnt}개 (한쪽으로 쏠리면 앱에서 섞어서 보여주세요)")


if __name__ == "__main__":
    main()
