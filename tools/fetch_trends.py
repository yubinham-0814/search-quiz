# -*- coding: utf-8 -*-
"""Google Trends 원본 내려받기 — 검색 40쌍을 data/raw/ 에 저장한다.

키도 로그인도 필요 없는 비공식 공개 엔드포인트를 쓴다.
쌍 목록은 trends-checklist.md 의 표에서 읽는다.
한 쌍을 받으려면 두 번 부른다: ① explore 로 토큰을 받고 ② 그 토큰으로 multiline(시계열)을 받는다.
받은 응답은 한 글자도 고치지 않고 그대로 저장한다 (")]}'" 머리글 포함).
값은 같은 그래프 안의 두 검색어끼리만 비교할 수 있는 상대지수(0~100)다.
주 단위라서 첫 행이 2025-12-28 주(1월 1일이 낀 주)부터 시작한다.

이미 받은 파일은 건너뛴다 (--force 를 주면 다시 받는다).

실행 (저장소 최상위에서):
    python tools/fetch_trends.py
    python tools/fetch_trends.py --force
"""
from __future__ import annotations

import http.client
import http.cookiejar
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

APP = Path(__file__).resolve().parent.parent
RAW = APP / "data" / "raw"
CHECKLIST = APP / "trends-checklist.md"
# HTTP 헤더는 latin-1 만 담는다. 한글을 넣으면 UnicodeEncodeError 가 난다
UA = {"User-Agent": "search-quiz/1.0 (data analysis class)"}
TIMEOUT = 90
PERIOD = "2026-01-01 2026-10-31"
GEO = "KR"

_opener = None


def _open(url: str) -> bytes:
    global _opener
    if _opener is None:
        jar = http.cookiejar.CookieJar()
        _opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        # 첫 방문에서 쿠키(NID)를 받아 둔다
        _opener.open(urllib.request.Request("https://trends.google.com/trends/?geo=KR", headers=UA),
                     timeout=TIMEOUT).read()
    with _opener.open(urllib.request.Request(url, headers=UA), timeout=TIMEOUT) as r:
        return r.read()


def _q(obj) -> str:
    return urllib.parse.quote(json.dumps(obj, ensure_ascii=False, separators=(",", ":")))


def fetch_pair(a: str, b: str) -> bytes:
    time.sleep(3)  # 구글에는 천천히 — 쌍마다 3초 이상 간격
    req = {"comparisonItem": [{"keyword": k, "geo": GEO, "time": PERIOD} for k in (a, b)],
           "category": 0, "property": ""}  # 모든 카테고리 · 웹 검색
    text = _open("https://trends.google.com/trends/api/explore?hl=ko&tz=-540&req=" + _q(req)).decode("utf-8")
    widgets = json.loads(text[text.index(chr(10)) + 1:])["widgets"]
    w = next(x for x in widgets if x["id"] == "TIMESERIES")
    time.sleep(1)
    data = _open("https://trends.google.com/trends/api/widgetdata/multiline?hl=ko&tz=-540"
                 "&req=" + _q(w["request"]) + "&token=" + w["token"])
    if b"timelineData" not in data:
        raise urllib.error.URLError("timelineData 가 없는 응답")
    return data


def pairs() -> list[dict]:
    out = []
    for line in CHECKLIST.read_text(encoding="utf-8").splitlines():
        c = [x.strip() for x in line.strip().strip("|").split("|")]
        if len(c) >= 6 and c[1].isdigit():
            out.append({"a": c[3], "b": c[4], "name": "trends_" + c[5].removesuffix(".csv") + ".json"})
    return out


def get(a: str, b: str, dest: Path, tries: int = 4) -> int:
    """잠깐의 실패(429·5xx·끊김)면 간격을 늘려 가며 다시 시도한다."""
    wait = 10
    for i in range(tries):
        try:
            data = fetch_pair(a, b)
            dest.write_bytes(data)
            return len(data)
        except urllib.error.HTTPError as e:
            if (e.code != 429 and e.code < 500) or i == tries - 1:
                raise
            why = str(e.code)
        except (http.client.IncompleteRead, urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if i == tries - 1:
                raise
            why = type(e).__name__
        print(f"          {why} — {wait}초 뒤 다시 시도합니다 ({i + 1}/{tries - 1})")
        time.sleep(wait)
        wait *= 2
    raise RuntimeError("도달 불가")


def main() -> int:
    force = "--force" in sys.argv
    RAW.mkdir(parents=True, exist_ok=True)
    todo = pairs()
    fail = 0
    for p in todo:
        dest = RAW / p["name"]
        if dest.exists() and not force:
            print(f"  건너뜀  {p['name']} 이미 있음")
            continue
        t0 = time.time()
        try:
            n = get(p["a"], p["b"], dest)
            print(f"  받음    {p['name']}  {n / 1024:.0f}KB  {time.time() - t0:.1f}s")
        except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.IncompleteRead) as e:
            print(f"  실패    {p['name']}  {e}")
            fail += 1
    print(f"\n총 {len(todo)}건 / 실패 {fail}건 · 저장 위치 {RAW}")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
