# 검색량 감 테스트 — 어느 것이 더 많이 검색되었을까?

8개 카테고리(아이돌·음식·유행어·게임·드라마/영화·스포츠·브랜드/앱·여행지) × 5문항.
두 키워드 중 **2026년 1~10월 한국 구글 검색**에서 더 많이 검색된 쪽을 고르면 정답입니다.
값은 Google Trends의 주별 상대지수이며, 같은 그래프 안의 두 검색어끼리만 비교할 수 있습니다.

## 폴더

| 경로 | 내용 |
|---|---|
| `index.html` `app.js` `style.css` | 앱 (원본은 기존 gam-test 앱을 복사) |
| `topics.json` `topics/` | 앱이 읽는 주제 목록과 문항 (자동 생성) |
| `trends-checklist.md` | 40쌍의 검색어·파일명 표 (쌍을 바꿀 때 여기를 고칩니다) |
| `data/raw/` | Google Trends 원본 응답 (받은 그대로, 배포 제외) |
| `tools/` | 받기·계산 코드 (배포 제외) |
| `api/comment.py` | 결과 촌평 함수 (기존 앱에서 복사) |

## 작업 순서 (저장소 최상위에서)

```
python tools/fetch_trends.py     # 원본 받기 (이미 있으면 건너뜀, --force 로 다시 받기)
python tools/build_topics.py     # 원본 → topics/*.json, topics.json, tools/정답지.md
python tools/build_quiz.py       # 점검용: 쌍별 정답·비율 요약 → quiz.json
python -m http.server 8200       # 로컬에서 열기
```

쌍을 바꾸면 `trends-checklist.md`를 고치고 `fetch_trends.py` → `build_topics.py` 순서로 돌립니다.
