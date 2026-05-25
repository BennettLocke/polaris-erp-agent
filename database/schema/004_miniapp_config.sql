CREATE TABLE IF NOT EXISTS miniapp_asset (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    scene VARCHAR(50) NOT NULL,
    name VARCHAR(80) NOT NULL,
    asset_url VARCHAR(600) NOT NULL DEFAULT '',
    active_asset_url VARCHAR(600) NOT NULL DEFAULT '',
    link_type VARCHAR(30) NOT NULL DEFAULT 'page',
    link_value VARCHAR(255) NOT NULL DEFAULT '',
    badge_text VARCHAR(20) NOT NULL DEFAULT '',
    subtitle VARCHAR(80) NOT NULL DEFAULT '',
    sort_order INT NOT NULL DEFAULT 0,
    enabled TINYINT(1) NOT NULL DEFAULT 1,
    extra_json LONGTEXT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_miniapp_asset_scene_name (scene, name),
    KEY idx_miniapp_asset_scene_enabled_sort (scene, enabled, sort_order, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO miniapp_asset
    (scene, name, asset_url, active_asset_url, link_type, link_value, badge_text, subtitle, sort_order, enabled, extra_json, created_at, updated_at)
VALUES
    ('home_banner', '首页主图', 'https://img.513sjbz.com/static/upload/images/app_nav/2026/04/25/1777104334795209.jpg', '', 'page', '/pages/category/index', '', '', 100, 1, NULL, NOW(), NOW()),
    ('bottom_tab', '首页', 'https://img.513sjbz.com/static/upload/images/app_center_nav/2026/03/30/1774869699282797.png', 'https://img.513sjbz.com/static/upload/images/app_center_nav/2026/03/30/1774869699200935.png', 'page', '/pages/home/index', '', '', 100, 1, NULL, NOW(), NOW()),
    ('bottom_tab', '分类', 'https://img.513sjbz.com/static/upload/images/app_center_nav/2026/03/30/1774869699309568.png', 'https://img.513sjbz.com/static/upload/images/app_center_nav/2026/03/30/1774869698249700.png', 'page', '/pages/category/index', '', '', 90, 1, NULL, NOW(), NOW()),
    ('bottom_tab', '订单列表', 'https://img.513sjbz.com/static/upload/images/app_center_nav/2026/03/30/1774869699858406.png', 'https://img.513sjbz.com/static/upload/images/app_center_nav/2026/03/30/1774869699328333.png', 'page', '/pages/orderflow/index', '', '', 80, 1, NULL, NOW(), NOW()),
    ('bottom_tab', '我的', 'https://img.513sjbz.com/static/upload/images/app_center_nav/2026/03/30/1774869699161830.png', 'https://img.513sjbz.com/static/upload/images/app_center_nav/2026/03/30/1774869699255558.png', 'page', '/pages/my/index', '', '', 70, 1, NULL, NOW(), NOW()),
    ('home_quick', '分类', '', '', 'page', '/pages/category/index', '', '', 100, 1, NULL, NOW(), NOW()),
    ('home_quick', '订单列表', '', '', 'page', '/pages/orderflow/index', '', '', 90, 1, NULL, NOW(), NOW()),
    ('home_quick', '我的', '', '', 'page', '/pages/my/index', '', '', 80, 1, NULL, NOW(), NOW()),
    ('home_quick', '搜索', '', '', 'page', '/pages/product/list', '', '', 70, 1, NULL, NOW(), NOW()),
    ('home_category', '半斤礼盒', '', '', 'search', '半斤礼盒', '30', '泡包装礼盒', 100, 1, NULL, NOW(), NOW()),
    ('home_category', '三两礼盒', '', '', 'search', '三两礼盒', '18', '泡包装礼盒', 90, 1, NULL, NOW(), NOW()),
    ('home_category', '二两礼盒', '', '', 'search', '二两礼盒', '12', '泡包装礼盒', 80, 1, NULL, NOW(), NOW()),
    ('home_category', '一两礼盒', '', '', 'search', '一两礼盒', '06', '泡包装礼盒', 70, 1, NULL, NOW(), NOW()),
    ('home_category', '6小盒礼盒', '', '', 'search', '6小盒礼盒', '12', '泡包装礼盒', 60, 1, NULL, NOW(), NOW()),
    ('home_category', '3小盒礼盒', '', '', 'search', '3小盒礼盒', '06', '泡包装礼盒', 50, 1, NULL, NOW(), NOW()),
    ('home_category', '2小盒礼盒', '', '', 'search', '2小盒礼盒', '02', '泡包装礼盒', 40, 1, NULL, NOW(), NOW()),
    ('home_category', '五格礼盒', '', '', 'search', '五格礼盒', '20', '泡包装礼盒', 30, 1, NULL, NOW(), NOW()),
    ('home_category', 'PVC礼盒', '', '', 'search', 'PVC礼盒', '', '半斤/三两/二两等', 20, 1, NULL, NOW(), NOW()),
    ('home_category', '快递纸箱', '', '', 'search', '快递纸箱', '', '30斤/20斤/15斤等', 10, 1, NULL, NOW(), NOW())
ON DUPLICATE KEY UPDATE
    asset_url=VALUES(asset_url),
    active_asset_url=VALUES(active_asset_url),
    link_type=VALUES(link_type),
    link_value=VALUES(link_value),
    badge_text=VALUES(badge_text),
    subtitle=VALUES(subtitle),
    sort_order=VALUES(sort_order),
    enabled=VALUES(enabled),
    extra_json=VALUES(extra_json),
    updated_at=NOW();
