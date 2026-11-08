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

- `hub.html` — 콘텐츠 현황판(관리용). **관리자 키**를 넣어야 열린다. 키는 브라우저 안에서만 쓰인다.
- `catalog.html` — 공개 카탈로그. 분야(대분류) → 중분류 → 소분류별 콘텐츠. `?embed=1`을 붙이면 머리글 없이 보여 주어 ahnboat.xyz에 끼워 넣기 좋다.
- `data/hub.csv.enc`, `data/hub.json.enc` — 관리 데이터(표·합본). 관리자 키로 잠긴 파일만 저장소에 있다(AES-256-GCM, 키는 PBKDF2-SHA256으로 유도). 평문 `hub.csv`·`hub.json`은 커밋하지 않는다(.gitignore).
- `data/catalog.json`, `data/servers.csv` — 공개 항목만 담은 파일. 카탈로그와 랩타운 서버실이 읽는다.
- `data/hub_meta.json` — 대분류(=서버실 랙 10개)·중분류 소개·색인어·그림, 첫 화면 배너.
- `scripts/hub_secure.py` — 잠긴 표를 풀어 `build_hub.py`로 다시 만들고 다시 잠근다. `scripts/hubcrypt.py` — 잠그기·풀기.
- 관리자 키는 저장소 Settings → Secrets and variables → Actions의 `HUB_KEY`에 있다. 매일 06시 수집과, `hub.csv.enc`·`hub_meta.json`을 올릴 때 다시 만든다.

### 표 고치는 순서
1. 현황판에서 키를 넣고 **엑셀용 표 내려받기**.
2. 엑셀에서 고친 뒤 CSV UTF-8로 저장.
3. 현황판의 **고친 표를 잠긴 파일로 만들기**에 넣어 `hub.csv.enc`를 받는다.
4. 저장소 `data/` 폴더에 `hub.csv.enc`를 올린다(덮어쓰기). 평문 `hub.csv`는 올리지 않는다.
