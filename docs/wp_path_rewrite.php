<?php
/*
 * ahnboat.xyz 공유 주소를 '#' 없는 진짜 경로로 쓰고 싶을 때만 넣는다 (선택).
 *   ahnboat.xyz/lab-server/rack01/concept-map  → 홈 화면을 그대로 보여 주고, 라우터 블록이 해당 랙을 연다.
 * 넣는 곳: 플러그인 'Code Snippets'의 새 스니펫(PHP, 어디서나 실행) — 테마 functions.php보다 안전.
 *   (WordPress.com 요금제는 Business 이상이어야 PHP 스니펫을 넣을 수 있다.)
 * 넣은 뒤: 관리자 → 설정 → 고유주소 → [변경사항 저장]을 한 번 눌러 주소 규칙을 새로 만든다.
 * 마지막으로 라우터 블록(docs/wp_router_block.html)의 MODE를 'path'로 바꾼다.
 * 그 뒤에도 예전 #/ 주소는 열리지 않으므로, 이미 #/ 주소를 공유했다면 MODE='hash'로 두는 편이 낫다.
 */
add_action('init', function () {
    $front = (int) get_option('page_on_front');
    $target = $front ? 'index.php?page_id=' . $front : 'index.php';
    add_rewrite_rule('^(lab-server|articles|portfolio|schedule|top)(/.*)?/?$', $target, 'top');
});
/* 워드프레스가 이 주소를 홈(/)으로 되돌려 보내지 않게 한다 */
add_filter('redirect_canonical', function ($redirect) {
    $p = trim(parse_url($_SERVER['REQUEST_URI'] ?? '', PHP_URL_PATH), '/');
    return preg_match('#^(lab-server|articles|portfolio|schedule|top)(/|$)#', $p) ? false : $redirect;
});
