# ahnboat lab 이미지 표지 현황

안상선(adminmrobo)의 해설 사이트들에 쓰인 **표지·장면 그림**을 한곳에서 보는 GitHub Pages 사이트입니다.

사이트: https://adminmrobo.github.io/ahnboat_lab_cover_status/

## 페이지 두 개

| 탭 | 주소 | 내용 |
|---|---|---|
| 전체 표지 현황 | `#all` | 저장소(와 GitHub 밖 시리즈)마다 카드 한 장. 대표 표지, 그림 수, 상태(정상 / 다시 그릴 그림 n장 / 정보 없음), 마지막 확인 날짜 |
| ↳ 온톨로지 연결 | `#all` 카드 | 저장소·사이트 주소, 페이지 안 지식 색인 `#kg`·온톨로지·서지 꾸러미 `#export` 링크와 저장소 안 온톨로지 파일(`KG_00_registry.json` 등), 상태(온톨로지 있음 / 일부만 / 없음) |
| ↳ 번역 현황 | `#all` 카드 | 언어 수와 언어별 페이지 수(ko·en·zh·ja·uz·ru·vi, 일부만 번역된 언어 표시), 언어별 첫 페이지 링크, README 언어 수. "한국어만"·"언어 빠짐" 필터 |
| 주판봇 변환 상황 | `#jupanbot` | 옛 하얀 로봇(Money-Robo)을 주판봇으로 다시 그릴 그림 (옛 그림은 따로 보관). 프롬프트 복사, 시리즈·우선순위 필터 |

## 매일 자동 수집

`.github/workflows/scan.yml`이 매일 한국 시간 오전 6시(와 Actions 탭의 수동 실행)에 `scripts/scan_repos.py`를 돌립니다.

1. adminmrobo의 공개 저장소를 모두 읽습니다 (`newsreporter_*`, 이 저장소, fork는 뺍니다).
2. 저장소마다 `cover_manifest.json`을 읽습니다. 없으면 그림 파일 이름(`cover`·`og`·`hero`·`thumb`·`sc_`)으로 표지를 추정합니다.
3. 사이트 HTML(저장소당 최대 40개)을 읽어 첫 페이지 제목, 온톨로지(`#kg`·`#export`, 온톨로지 파일), 번역 언어를 셉니다.
4. 결과를 `data/repos.json`에 씁니다.
5. 지난 수집 뒤로 바뀐 저장소만 받아 `scripts/make_thumbs.py`가 카드 대표 그림(`thumbs/repos/<저장소>.jpg`)을 다시 만듭니다. 썸네일은 **지금 사이트에 걸린 그림**을 기준으로 하며, 고르는 순서는 `cover_manifest.json`의 표지 → 다시 그리기 목록의 표지·첫 화면 그림 → `og:image` → 파일 이름(`cover`·`og`·`hero`·`thumb`, 없으면 `sc_`) → 본문 장면 → 페이지에 박힌 첫 화면 그림입니다. 무엇을 골랐는지는 `thumbs/repos/_index.json`에 남습니다.
6. 바뀐 것이 있으면 `github-actions[bot]`이 커밋합니다.

**새 해설 저장소를 만들 때 `cover_manifest.json`을 맨 위 폴더에 넣으면 다음 날 자동으로 잡힙니다.** 규격은 [`docs/cover_manifest_schema.md`](docs/cover_manifest_schema.md), 예시는 [`docs/cover_manifest.example.json`](docs/cover_manifest.example.json).

## 데이터 파일

| 파일 | 누가 고치나 | 내용 |
|---|---|---|
| `data/repos.json` | 자동 수집 | 저장소별 현황 |
| `data/external.json` | 관리자 | **GitHub 밖 시리즈** — 웹 결과물 페이지, zip으로만 전달한 시리즈(DLSS 3부작 등). 새 시리즈가 생기면 여기에 한 줄 더합니다 |
| `data/redraw.json` | 관리자 | 다시 그릴 그림 (R·A 번호, 프롬프트, 비율, 반영 위치 `targets`). 2026-11-07에 R107~R121(15장) 추가 |
| `data/redraw_status.json` | 관리자 (커밋) | 그림별 진행 상태 `todo` / `received` / `applied`, 날짜, 메모 |
| `data/old_robot.json` | 관리자 | 옛 하얀 로봇의 글 표기·표정 그림이 남은 저장소. 카드에 "옛 로봇 글·표정 남음" 표시 |
| `thumbs/` | 관리자·자동 수집 | 카드 썸네일. `R001.jpg`…·`A001.jpg`…는 지금 사이트에 걸린 그림, `before/`는 바꾸기 전 옛 그림, `repos/<저장소>.jpg`는 저장소 대표 그림(자동), `refs/`는 참조 그림 |

## GitHub Pages 켜기

Settings → Pages → Build and deployment → Source: **Deploy from a branch** → Branch: **main** / **(root)** → Save.
몇 분 뒤 위 주소에서 열립니다.

## 로컬에서 보기·수집하기

```bash
python3 -m http.server 8000         # http://localhost:8000/ (파일을 바로 열면 data/*.json 을 못 읽습니다)
GITHUB_TOKEN=... python3 scripts/scan_repos.py
# API를 못 쓸 때: 저장소 사본(git clone)으로 같은 형식 만들기
python3 scripts/scan_repos.py --local --list list.txt --repos-dir ./repos
python3 scripts/make_thumbs.py --repos-dir ./repos --all   # Pillow 필요: 대표 그림 썸네일 모두 다시 만들기
python3 scripts/make_thumbs.py --fetch                     # 바뀐 저장소만 받아서 (Actions와 같은 방식)
```

글 · 안상선 ((주)M-Robo 대표)

## 콘텐츠 현황판 · 공개 카탈로그

- `hub.html` — 콘텐츠 현황판. GitHub 저장소와 GitHub 밖 실적(논문·특허·저서·사업)을 한 표로 보여 준다.
- `catalog.html` — 공개 카탈로그. 분야(대분류) → 갈래(중분류) → 주제(소분류) → 콘텐츠 순서로 (소분류가 하나뿐인 갈래는 바로 콘텐츠로) 들어간다. `?embed=1`을 붙이면 머리글 없이 보여 주어 다른 사이트(ahnboat.xyz)에 끼워 넣기 좋다.
- `data/hub.csv` — 사람이 고치는 표(엑셀). 제목, 주요내용, 대분류, 중분류, 소분류, 공개대상여부, 연구실 시리즈·외국어팩·온톨로지 대상 여부, 순서, 외부링크, 비고.
- `data/hub_meta.json` — 대분류 이름·순서·색·외국어 이름. 순서가 랩타운 지하 1층 서버실의 랙 순서(최대 10개).
- `scripts/build_hub.py` — `hub.csv`와 매일 수집한 `repos.json`을 합쳐 `data/hub.json`(현황판·카탈로그)과 `data/servers.csv`(서버실)를 만든다. 새 저장소는 `미분류 · 검토`로 자동 추가된다.
- `hub.csv`나 `hub_meta.json`을 올리면 Actions가 바로 다시 만든다.
