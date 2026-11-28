# 하루의 실험실 썸네일 규격 (2026-11-28)

홈 '조수 하루의 3차원 실험실' 막대와 전체 회차 화면(`haru_lab.html`)의 카드 그림 규격입니다. 회차가 늘어도 한 시리즈로 보이게, 모든 회차를 이 규격 하나로 맞춥니다.

## 1. 파일

| 항목 | 값 |
|---|---|
| 비율·크기 | **16:9 · 960×540** (카드 틀도 16:9, 잘림 없음) |
| 형식 | WebP, 품질 82, 150 KB 이하 |
| 이름·자리 | `thumbs/haru_lab/epNN.webp` (`data/haru_lab.json`의 `thumb`) |
| 만들기 | `python3 scripts/haru_thumb.py <원본> <회차 번호>` — 가운데 기준으로 16:9에 맞춰 자르고 LANCZOS로 줄인다. 원본은 Genspark에서 받은 큰 그림(2048×1152 등)을 쓴다 |

## 2. 그림

| 항목 | 규칙 |
|---|---|
| 그림체 | **16비트 RPG풍 고해상도 픽셀아트** (가로 1600 이상에서 그린 촘촘한 픽셀, 큰 네모 블록 금지) — EP.06·EP.07이 기준 |
| 배경 | 밝은 연구실 바닥 또는 크림색 좌표 바닥 + **3D 좌표축 세 개**(x 주황 · y 초록 · z 파랑) — 시리즈 표시 |
| 인물 | **조수 하루는 반드시 등장**(왼쪽 앞, 얼굴이 카드 가운데 띠 안). 그 회차 진행 식구를 함께(주판봇·초파리 연구원·인턴 시아·모아, X1~X3는 실루엣) |
| 소재 | 그 회차 실험을 글자 없이 보여 주는 소품 하나 (드롭아웃 → 반쯤 꺼진 뉴런 전구 등) |
| 글자 | **그림 안 글자·숫자·로고 금지**. EP 번호·제목·숫자는 카드가 붙인다 (EP.05 옛 썸네일처럼 글자를 넣지 않는다) |
| 안전 영역 | 얼굴·핵심 소품은 가운데 80% 안쪽. 왼쪽 위 120×40은 비워 둔다(EP 배지 자리) |
| 금지 | 화면 캡처·그래프 캡처를 그대로 쓰는 것 (임시로만) |

## 3. 지금 상태

**2026-11-28 — 8편 모두 같은 지시문 틀로 새로 받아 바꿨다(규격 완료).** 원본은 Genspark 2048×1152 PNG, 홈에는 960×540 WebP(60~91 KB).
새 회차는 같은 틀(공통 머리말 + 회차 장면)과 같은 참고 그림으로 한 장 더 받아 `scripts/haru_thumb.py`로 넣는다.

## 4. Genspark 지시문

참고 그림: 그림체 기준 EP.06·EP.07 썸네일 원본 + 캐릭터 설정샷 `fruitfly-lab-expressions/images/_sheets/lab6_lineup.png`(박사·하루·시아·모아·주판봇·초파리), `interns_turnaround8.png`(위 시아 · 아래 모아), `haru_A.png`. 모두 `haru_lab_prompts_all.zip`의 `3_references/`에 들어 있다.

### 공통 머리말 (모든 회차에 그대로)

```
16:9, 2048×1152. 첨부한 EP.06·EP.07 썸네일과 같은 그림체·같은 캐릭터 외형으로 그려 줘.
Art style (required): 16-bit RPG style pixel art rendered natively at high resolution with small, dense pixels (NOT a small image blown up into big blocks), bold dark outline, 2-3 tone shading, bright clean lab lighting.
Setting: a bright laboratory floor with a 3D coordinate system — x axis orange, y axis green, z axis blue — meeting near the center.
Haru (pink hair with two round buns and a navy streak, blue eyes, white lab coat over lavender hoodie) at the front left, friendly and curious.
Keep faces and the key prop inside the central 80%; keep the top-left corner simple (a label will be placed there).
No text, no letters, no numbers, no logos anywhere in the image.
```

### EP.01 뉴런의 드롭아웃

```
Scene: Haru stands beside a small neural network made of glowing bulbs connected by wires, floating above the 3D axes; about half of the bulbs are switched off (dim gray) and the other half glow warmly, as if a coin decided which ones rest. Haru holds a big coin in one hand, mid-flip.
Mood: playful experiment, "turn half off and it learns better".
```

### EP.02 얼려 두고 덧붙이는 LoRA

```
Scene: a large block of ice containing a glowing grid (a frozen weight matrix) sits on the 3D floor; Haru attaches two thin glowing panels (one tall and thin, one wide and thin) onto its side like a small adapter, while a flipped (upside-down) handwritten-style digit shape glows on a little board nearby — drawn as a shape only, not a readable number.
Mood: careful, clever "freeze the big part, add a thin layer".
```

### EP.03 필터를 미끄러뜨리는 망 (CNN)

```
Scene: Haru slides a small 3×3 glowing magnifier tile across a large pixel picture of a cat face lying on the 3D floor; behind it, a stack of translucent feature-map sheets rises along the y axis. A second, identical cat face is shifted to the right and is still recognized (a soft green glow around it).
Mood: "same filter everywhere — it still finds the cat".
```

### EP.08 박사의 과제 — 최적화 연습

다른 회차와 같이 **썸네일 지시서로 새로 만든다**. 장면만 저장소 `haru_3d_optimization_01`의 1부 표지(cover_part1)와 같게 한다. 저장소 지시서의 "홈 썸네일은 1부 표지를 씁니다" 문장은 이 규격으로 대체됐다.

받은 그림은 `python3 scripts/haru_thumb.py <받은 그림> 01` 처럼 넣고, 위 표의 상태를 고칩니다.
