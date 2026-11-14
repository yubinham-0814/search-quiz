# -*- coding: utf-8 -*-
"""Google Trends 원본 → 8카테고리 × 5문항 = 40문항.

**모든 숫자는 data/raw/ 의 원본에서 계산합니다.** 지어낸 값이 없어야 합니다.
결과는 앱이 읽는 topics/*.json · topics.json 과, 사람이 읽는 tools/정답지.md 로 나갑니다.
정답지와 이 스크립트는 .vercelignore 에 들어 있어 배포되지 않습니다.

원본: data/raw/trends_NN_*.json (tools/fetch_trends.py 가 받아 둔 응답 그대로).
쌍 목록은 trends-checklist.md 의 표에서 읽는다. 값은 주별 상대지수(0~100)이고,
2026-01-01 ~ 2026-10-31 에 시작하는 주를 합산한다(12/28 주는 제외).
정답 = 합계가 더 큰 쪽을 클릭하는 것. 근거 = 큰 쪽 ÷ 작은 쪽 (소수 첫째 자리).
'<1' 로 표기된 주는 0.5 로 센다.

실행 (저장소 최상위에서):
    python tools/build_topics.py
"""
from __future__ import annotations

import datetime as dt
import io
import json
import sys
from pathlib import Path

# 윈도우 콘솔(cp949)은 이모지 · 기호를 못 찍고 멈춘다. 출력만 UTF-8 로 맞춘다
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

HERE = Path(__file__).resolve().parent          # tools/
APP = HERE.parent                                # 저장소 최상위 = 배포되는 곳
RAW = APP / "data" / "raw"
OUT = APP / "topics"

TR_START, TR_END = dt.date(2026, 1, 1), dt.date(2026, 10, 31)
TR_TEXT = "어느 것이 더 많이 검색되었을까?"
TR_SOURCE = "Google Trends (웹 검색, 상대지수)"
TR_URL = "https://trends.google.co.kr/"

# 카테고리 → (주제 id, 이모지, 제목, 문항 id 머리글). 초안 — 나중에 고칩니다
TR_CATS = {
    "아이돌":      ("search-idol",   "🎤", "검색 대결: 아이돌",      "idol"),
    "음식":        ("search-food",   "🍜", "검색 대결: 음식",        "food"),
    "유행어":      ("search-slang",  "💬", "검색 대결: 유행어",      "slang"),
    "게임":        ("search-game",   "🎮", "검색 대결: 게임",        "game"),
    "드라마/영화": ("search-movie",  "🎬", "검색 대결: 드라마/영화", "movie"),
    "스포츠":      ("search-sport",  "⚽", "검색 대결: 스포츠",      "sport"),
    "브랜드/앱":   ("search-brand",  "📱", "검색 대결: 브랜드/앱",   "brand"),
    "여행지":      ("search-travel", "✈️", "검색 대결: 여행지",      "travel"),
}
BLURB = "2026년 1~10월, 한국 구글 검색 기준"

TOPICS: list[dict] = []


def topic(tid, emoji, title, blurb, source, source_url, questions, caveat=""):
    TOPICS.append({"id": tid, "emoji": emoji, "title": title, "blurb": blurb,
                   "source": source, "source_url": source_url,
                   "caveat": caveat, "questions": questions})


def choice(qid, text, options, answer, basis, why):
    assert answer in options, f"{qid}: 정답이 선택지에 없습니다"
    return {"id": qid, "type": "choice", "text": text, "options": options,
            "answer": answer, "basis": basis, "why": why}


def josa(word, with_batchim, without):
    """받침 유무로 조사를 고른다 (한글 · 숫자 · 영문 끝글자)."""
    ch = word[-1]
    if "가" <= ch <= "힣":
        has = (ord(ch) - 0xAC00) % 28 != 0
    elif ch.isdigit():
        has = ch in "013678"            # 영·일·삼·육·칠·팔
    else:
        has = ch.upper() in "LMNR"      # 엘·엠·엔·알
    return with_batchim if has else without


def trends_totals(path):
    """원본 응답에서 기간 안 주의 합계 (a, b) 와 쓴 주 수. '<1' 은 0.5 로 센다."""
    text = path.read_text(encoding="utf-8")
    rows = json.loads(text[text.index(chr(10)) + 1:])["default"]["timelineData"]
    tot, n = [0.0, 0.0], 0
    for r in rows:
        d = dt.datetime.fromtimestamp(int(r["time"]), dt.timezone.utc).date()
        if not (TR_START <= d <= TR_END):
            continue
        n += 1
        for k in range(2):
            tot[k] += 0.5 if r["formattedValue"][k] == "<1" else float(r["value"][k])
    return tot, n


def build_trends_topics():
    pairs = []
    for line in (APP / "trends-checklist.md").read_text(encoding="utf-8").splitlines():
        c = [x.strip() for x in line.strip().strip("|").split("|")]
        if len(c) >= 6 and c[1].isdigit():
            pairs.append({"n": int(c[1]), "cat": c[2], "a": c[3], "b": c[4],
                          "file": "trends_" + c[5].removesuffix(".csv") + ".json"})
    by_cat = {}
    weeks = set()
    for g, p in enumerate(pairs):                 # g = 전체 순번 0..39
        (ta, tb), n = trends_totals(RAW / p["file"])
        weeks.add(n)
        win, lose = (p["a"], p["b"]) if ta > tb else (p["b"], p["a"])
        ratio = max(ta, tb) / min(ta, tb)
        # 정답 위치를 번갈아 배치한다: 짝수 번째는 첫째 보기, 홀수 번째는 둘째 보기
        options = [win, lose] if g % 2 == 0 else [lose, win]
        basis = (f"{win}{josa(win, '이', '가')} {lose}보다 {ratio:.1f}배 "
                 "더 많이 검색되었습니다.")
        cat = TR_CATS[p["cat"]]
        by_cat.setdefault(p["cat"], []).append(
            choice(f"{cat[3]}{len(by_cat.get(p['cat'], [])) + 1}", TR_TEXT,
                   options, win, basis, ""))
    assert len(weeks) == 1, f"쌍마다 쓴 주 수가 다릅니다: {weeks}"
    nweeks = weeks.pop()
    caveat = (f"구글 트렌드는 검색 횟수가 아니라, 같은 그래프 안의 두 검색어끼리만 비교할 수 "
              f"있는 상대지수입니다. 2026년 1월 4일 주부터 10월 31일까지 {nweeks}주를 "
              "합산했고, 철자가 같은 다른 대상(사람 이름·일반 단어)의 검색이 섞여 있을 수 있습니다.")
    for cname, qs in by_cat.items():
        tid, emoji, title, _ = TR_CATS[cname]
        topic(tid, emoji, title, BLURB, TR_SOURCE, TR_URL, qs, caveat=caveat)


def main() -> None:
    build_trends_topics()
    OUT.mkdir(parents=True, exist_ok=True)
    index = []
    for t in TOPICS:
        assert len(t["questions"]) == 5, f"{t['id']}: 문항이 5개가 아닙니다"
        pack = {k: t[k] for k in ("id", "emoji", "title", "blurb",
                                  "source", "source_url", "caveat")}
        pack["questions"] = t["questions"]
        io.open(OUT / f"{t['id']}.json", "w", encoding="utf-8").write(
            json.dumps(pack, ensure_ascii=False, indent=2))
        index.append({k: t[k] for k in ("id", "emoji", "title", "blurb", "source")})

    # 제목·부제는 화면을 바꾸며 고친 값을 지킨다 — 있던 topics.json 에서 읽어 쓴다
    old = {}
    if (APP / "topics.json").exists():
        try:
            old = json.load(io.open(APP / "topics.json", encoding="utf-8"))
        except ValueError:
            old = {}
    io.open(APP / "topics.json", "w", encoding="utf-8").write(json.dumps({
        "title": old.get("title", "감 테스트"),
        "subtitle": old.get("subtitle", "어떤 것이 가장 많이 검색되었을까?"),
        "grades": old.get("grades", [
            {"min": 90, "name": "촉이 데이터급", "emoji": "🎯"},
            {"min": 70, "name": "감이 좋은 편", "emoji": "📊"},
            {"min": 50, "name": "보통의 감각", "emoji": "🙂"},
            {"min": 30, "name": "느낌대로 삽니다", "emoji": "🎲"},
            {"min": 0, "name": "감은 접어두시죠", "emoji": "🙈"},
        ]),
        "reactions_choice": old.get("reactions_choice",
                                    {"hit": "맞히셨습니다", "miss": "다들 그렇게 찍습니다"}),
        "reactions": old.get("reactions", [
            {"max": 5, "text": "촉이 좋으시네요"},
            {"max": 20, "text": "비슷하게 보셨습니다"},
            {"max": 60, "text": "음…"},
            {"max": 999, "text": "꽤 멀리 가셨습니다"},
        ]),
        "topics": index,
    }, ensure_ascii=False, indent=2))

    # 사람이 읽는 정답지
    md = [f"# 문항 정답지 — {len(TOPICS)}주제 "
          f"{sum(len(t['questions']) for t in TOPICS)}문항", "",
          "> 모든 값은 `data/raw/` 의 원본에서 `tools/build_topics.py` 가 계산합니다.", ""]
    for t in TOPICS:
        md += [f"## {t['emoji']} {t['title']}", "",
               f"- 출처: {t['source']} · {t['source_url']}"]
        if t["caveat"]:
            md += [f"- **한계** {t['caveat']}"]
        md += [""]
        for q in t["questions"]:
            md += [f"**{q['text']}** ({' / '.join(q['options'])})", "",
                   f"- 정답 **{q['answer']}**", f"- 근거 {q['basis']}", ""]
    io.open(HERE / "정답지.md", "w", encoding="utf-8").write("\n".join(md))

    print(f"주제 {len(TOPICS)}개 · 문항 {sum(len(t['questions']) for t in TOPICS)}개")
    for t in TOPICS:
        print(f"\n{t['emoji']} {t['title']}")
        for q in t["questions"]:
            print(f"    {' / '.join(q['options']):<30} → {q['answer']}  ({q['basis']})")


if __name__ == "__main__":
    main()
