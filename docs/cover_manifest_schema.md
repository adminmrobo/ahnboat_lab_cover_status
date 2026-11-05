# cover_manifest.json 규격

해설 사이트 저장소의 **맨 위 폴더**에 `cover_manifest.json`을 두면, 이 현황판이 매일 아침 그 파일을 읽어 표지·장면 그림 목록과 상태를 보여 줍니다. 파일이 없으면 이름에 `cover`·`og`·`hero`·`thumb`·`sc_`가 들어간 그림 파일을 찾아 "추정 표지"로만 적습니다.

예시: [`cover_manifest.example.json`](cover_manifest.example.json)

## 맨 위 필드

| 필드 | 뜻 |
|---|---|
| `series_ko` | 시리즈 이름 (현황판 카드 제목) |
| `title_ko` | 이 사이트(편)의 제목 |
| `site_url` | GitHub Pages 주소 |
| `site_title` | (선택) 사이트 첫 페이지 제목. 없으면 `index.html`의 `<title>`(없으면 `<h1>`)을 씁니다 |
| `ontology` | (선택) 온톨로지 연결. `pages`: 페이지마다 `{"path", "kg": true, "export": true}` — `kg`는 지식 색인 `id="kg"`, `export`는 온톨로지·서지 꾸러미 `id="export"`가 있는지. `files`: 저장소 안 온톨로지 파일 경로(`KG_00_registry.json`, `*.jsonld`, `*.ttl`, `kg.json`, `nodes.csv`·`edges.csv`, `backbone_*.json`) |
| `i18n` | (선택) 번역 현황. `langs`: 언어 코드(`ko` `en` `zh` `ja` `uz` `ru` `vi`), `pages`: 언어별 페이지 수, `readme_langs`: README에 들어 있는 언어 |
| `languages` | (선택) 언어 코드 목록만 적을 때. 예: `["ko","en","zh"]` |
| `items` | 그림 목록 (아래) |
| `updated` | 이 파일을 고친 날짜 `YYYY-MM-DD` |

## items 한 줄 = 그림 한 장

| 필드 | 값 | 뜻 |
|---|---|---|
| `id` | 문자열 | 저장소 안에서 겹치지 않는 이름 (`cover`, `og`, `sc_meeting` …) |
| `role` | `cover` `og` `thumb` `hero` `scene` `outro` `banner` | 그림이 쓰이는 자리 |
| `path` | 저장소 안 경로 | 그림이 **파일**일 때 |
| `embedded_in` + `key` | HTML 경로 + CSS 선택자 | 그림이 HTML 안에 **base64로 박혀** 있을 때 (`path` 대신) |
| `size` | `[가로, 세로]` | 픽셀 크기 |
| `characters` | `doc` `asst` `fly` `jupanbot` 중 여럿 | 그림에 나오는 캐릭터 (박사·조수 하루·초파리 연구원·주판봇) |
| `robot` | `jupanbot-v2` `jupanbot-v1` `money-robo` `none` | 그림 속 로봇의 판. `money-robo`는 옛 하얀 로봇 |
| `prompt_en` | 문자열 또는 `null` | 다시 그릴 때 쓰는 영어 프롬프트 |
| `source_of` | `null` 또는 다른 `id` | 원본이면 `null`, 크기별 사본이면 원본의 `id` (사본은 원본을 받아 잘라 만듦) |
| `status` | `ok` `redraw` `received` | 정상 / 다시 그려야 함 / 새 그림을 받았고 반영 전 |

## 온톨로지·번역은 실제 파일을 우선합니다

현황판은 매일 사이트 HTML을 직접 읽어 온톨로지와 번역 현황을 셉니다. 매니페스트의 `ontology`·`i18n`·`languages`는 HTML을 읽을 수 없을 때의 참고값입니다.

- **온톨로지 상태**: 원본(번역판이 아닌) 페이지 모두에 `#kg`가 있으면 `full`(온톨로지 있음), 일부만 있으면 `partial`, 없으면 `none`.
- **번역 언어**: 언어 폴더(`en/` …)나 파일 이름 끝(`page.en.html`, `page_en.html`, `page-en.html`)으로 언어를 정하고, 원본 페이지는 `<html lang>`을 따릅니다(없으면 `ko`). 언어별 페이지 수가 가장 많은 언어보다 적으면 "일부"로 표시합니다. `?lang=` 주소는 세지 않습니다. README의 언어 섹션은 페이지 수와 따로 `readme_langs`로 적습니다.
- 옮겨 가기만 하는 작은 페이지(meta refresh)와 `<html>` 없는 조각 파일, `src/`·`dist/`·`archive/` 같은 폴더의 HTML은 페이지로 세지 않습니다.

## 규칙

- `robot`이 `money-robo`이면 `status`는 `redraw`로 둡니다.
- 같은 그림의 크기별 사본(og, thumb)은 `source_of`로 원본에 묶습니다. 현황판은 원본만 "다시 그릴 그림"으로 셉니다.
- 새 해설 저장소를 만들 때 이 파일을 함께 넣으면 다음 날 아침 수집에서 자동으로 잡힙니다.
