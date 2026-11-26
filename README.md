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

`.github/workflows/scan.yml`이 하루 두 번(예약 03:27·15:27 KST — GitHub 사정으로 몇 시간 밀려 보통 아침·저녁에 실행)과 Actions 탭의 수동 실행 때 `scripts/scan_repos.py`를 돌립니다.

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
| `data/series_cards.json`, `data/series/` | 관리자 · 자동 수집 | **장(챕터)별 시리즈 카드** — 한 저장소 안 여러 편(예: 인퍼런스 스터디 북)을 카탈로그에서 장별 소분류로 묶는다. 제목·소개·썸네일은 시리즈 저장소의 `catalog_cards.json`이 기준이며 매일 수집 때 새로 받는다. 키 없이 바로 반영: `python3 scripts/series_cards.py` |
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

- `growth_crime.html` — **AI 범죄학 지식 노드 현황**. growth.html의 AI 범죄 전용판. 데이터는 ai_crime_lab의 `data/crime_kg.json`(AI 범죄학 뼈대 13개 영역)을 `scripts/build_growth_crime.py`가 받아 `data/growth_crime.json`으로 만든다(하루 두 번, scan.yml).
- `admin.html` — **콘텐츠 관리실**. 비밀번호로 들어가 표를 바로 고치고 저장한다(아래 설명).
- `hub.html` — 콘텐츠 현황판(관리용). **관리자 키**를 넣어야 열린다. 키는 브라우저 안에서만 쓰인다.
- `catalog.html` — 공개 카탈로그. 분야(대분류) → 중분류 → 소분류별 콘텐츠. `?embed=1`을 붙이면 머리글 없이 보여 주어 ahnboat.xyz에 끼워 넣기 좋다.
- `data/hub.csv.enc`, `data/hub.json.enc` — 관리 데이터(표·합본). 관리자 키로 잠긴 파일만 저장소에 있다(AES-256-GCM, 키는 PBKDF2-SHA256으로 유도). 평문 `hub.csv`·`hub.json`은 커밋하지 않는다(.gitignore).
- `data/catalog.json`, `data/servers.csv` — 공개 항목만 담은 파일. 카탈로그와 랩타운 서버실이 읽는다.
- `data/publish_settings.json` — 저장 기준일(`mode` auto=매일 그날 / fixed=`base_date`). 관리실이 저장한다.
- `data/admin_vault.enc` — 관리실 열쇠 보관함(비밀번호로 잠김).
- `data/hub_meta.json` — 대분류(=서버실 랙 10개)·중분류 소개·색인어·그림, 첫 화면 배너. 랙은 콘텐츠의 주제 분류다(2026-11-21 개편: RACK 05 경제·수학·최적화, RACK 08 인공지능 응용).
- `data/rack_migration.json` — 랙 개편 옮기기 표와 상시 규칙(rules: 좌표 공간·벡터·라그랑지안·해밀토니안 저장소는 늘 RACK 05 경제·수학·최적화 › 좌표·벡터 공간, 검토 중이면 공개로 연다). 빌드할 때 대분류가 `from`과 같은 행만 새 분류로 옮기고 논문 해설이던 행에는 주인장 저자(Y)·`Articles_갈래`를 단다(관리표 hub.csv 자체가 고쳐져 다시 잠긴다). 한 번 옮긴 뒤에는 관리실에서 고친 분류를 덮어쓰지 않는다.
- `scripts/hub_secure.py` — 잠긴 표를 풀어 `build_hub.py`로 다시 만들고 다시 잠근다. `scripts/hubcrypt.py` — 잠그기·풀기.
- 관리자 키는 저장소 Settings → Secrets and variables → Actions의 `HUB_KEY`에 있다. 하루 두 번 예약 수집과, `hub.csv.enc`·`hub_meta.json`을 올릴 때 다시 만든다.

### 콘텐츠 관리실 (`admin.html`) — 화면에서 바로 고치고 저장

https://adminmrobo.github.io/ahnboat_lab_cover_status/admin.html

- **관리자 비밀번호 하나**로 들어간다. 이 비밀번호가 곧 관리자 키다 — 내용 표(`hub.csv.enc`)·현황판(`hub.html`)·방문 레포트가 모두 이 비밀번호로 잠긴다. 비밀번호는 저장소 어디에도 평문으로 없고, GitHub에는 Settings → Secrets and variables → Actions의 **`ADMIN_PASSWORD`**로만 둔다.
  - 관리자 키 바꾸기: `ADMIN_PASSWORD`를 새 값으로 넣고(또는 고치고) Actions → **표지 현황 수집** → Run workflow. `scripts/rekey.py`가 예전 키(`HUB_KEY`)로 잠긴 파일을 새 비밀번호로 다시 잠근다. `ADMIN_PASSWORD`가 있으면 Actions는 그 값을 관리자 키로 쓴다.
- 처음 한 번: 비밀번호로 들어가면 **저장용 GitHub 토큰**(Fine-grained, Contents: Read and write)을 묻는다. 토큰은 비밀번호로 잠가(PBKDF2 60만 회) `data/admin_vault.enc`에 두므로, 다음부터는 어느 기기에서든 비밀번호만 넣으면 된다. 토큰이 만료되면 같은 화면에서 다시 등록한다.
- 표의 모든 칸을 화면에서 고친다(공개·공개일·순서·시리즈물은 표에서 바로, 나머지는 **편집**). **저장**(Ctrl/⌘+S)을 누르면 표를 관리자 키로 잠가 `data/hub.csv.enc`와 `data/publish_settings.json`을 커밋 하나로 올리고, 몇 분 뒤 Actions가 카탈로그·서버실을 다시 만든다.
- **저장 기준일**: 공개 Y이면서 **공개일**이 기준일 이전(같은 날 포함)인 콘텐츠만 카탈로그·서버실에 나온다. 공개일이 비면 바로 나온다. "매일 그날 날짜로"를 켜면 하루 두 번 예약 수집 때 그날이 기준일이 되어 예약해 둔 콘텐츠가 날짜에 맞춰 자동으로 나온다. 끄면 저장할 때 고른 날짜로 고정된다.
- **시리즈물**: 여러 챕터를 하나로 묶은 콘텐츠(예: 베이지안 통계학 13회차)는 시리즈물에 표시하고 **챕터**를 연다. "저장소 HTML에서 챕터 불러오기"로 파일·제목·소개를 가져오고, "첫 장부터 간격(일)대로 채우기"로 매주 한 장씩 같은 공개 일정을 한 번에 넣을 수 있다. 공개된 챕터만 카탈로그 카드의 "시리즈 · n장 공개" 목록에 소개되고, 다음 공개 예정일이 함께 보인다.
  - 표에서 챕터는 `상위시리즈`=시리즈 저장소, `저장소`=`<시리즈 저장소>/<파일>` 인 줄이다. 카탈로그 카드는 상위 줄 하나만 만들고, 서버실 목록에는 챕터가 따로 들어가지 않는다.
  - 카탈로그에 소개하지 않는 것일 뿐, 챕터 HTML 자체는 GitHub Pages에서 주소로 열 수 있다.
- 엑셀로 고치고 싶을 때는 관리실의 **CSV 내려받기 → 엑셀 → CSV 불러오기 → 저장**으로 끝난다(잠그는 단계가 따로 없다).

### 표 고치는 순서 (예전 방식 · 관리실을 못 쓸 때)
1. 현황판에서 키를 넣고 **엑셀용 표 내려받기**.
2. 엑셀에서 고친 뒤 CSV UTF-8로 저장.
3. 현황판의 **고친 표를 잠긴 파일로 만들기**에 넣어 `hub.csv.enc`를 받는다.
4. 저장소 `data/` 폴더에 `hub.csv.enc`를 올린다(덮어쓰기). 평문 `hub.csv`는 올리지 않는다.

## 홈페이지(ahnboat.xyz)에 붙이는 화면

- `catalog.html` — Reon Ahn's Lab Server (콘텐츠 10개 랙)
- `catalog.html?view=articles` — Ahn's Articles & Presentations. 주인장이 직접 쓴 논문·학술대회 발표만 모은다. 랙 이름이 아니라 관리실의 **주인장 저자** 체크(hub.csv `주인장_저자_여부` = Y)로 모이고, 체크하지 않으면 Articles(논문·발표·강연)에서 빠진다. 관리실의 **저자강의** 체크(`저자_강의_여부` = Y)는 LECTURE 갈래로 모인다. 논문 갈래는 `Articles_갈래` 칸(AI 응용 논문·경제·사회 논문·금융·자산 논문·외부_콘텐츠, 비우면 기타 논문·발표). 그래서, 같은 글이 Lab Server에서는 주제에 맞는 랙에 들어 있다.
- `catalog.html?view=portfolio` — Ahn's Portfolio. 목록은 `data/portfolio.csv`(엑셀로 고쳐 그대로 올림: 대분류, 중분류, 제목, 소개, 링크, 이미지, 버튼글씨, 비고, 순서, 공개), 추가링크 — "버튼글씨|주소"를 ; 로 이어 쓰면 보조 버튼이 붙는다(예: 저서 카드의 보충본·Lab Server 위치), 분야 설정은 `data/portfolio_meta.json`. 링크가 비면 '링크 준비 중'.
- `haru_lab.html` — **하루의 실험실** 연재 블록. 홈 'Reon Ahn Page 지식 노드 현황'(growth.html) 바로 위. 회차는 `data/haru_lab.json`의 episodes에 한 줄씩 더하고(썸네일은 `thumbs/haru_lab/`), 워드프레스에 붙이는 코드는 `docs/wp_haru_lab_block.html`. 바로가기 주소 `ahnboat.xyz/#haru-lab`.
- `progress.html` — Progress Board. 공개 콘텐츠만, 랙별 온톨로지·외국어팩 진행, 언어별 콘텐츠, 최근 업데이트, 다음에 손볼 곳.
- 화면 설정(제목·배너·갈래 이름 바꾸기)은 `data/views.json`.
- 모두 `?embed=1&theme=light`를 붙여 끼워 넣으면 머리글 없이 보이고, 높이를 바깥 페이지에 알려 준다.

