CREATE TABLE IF NOT EXISTS number_sequence_setting (
    sequence_key VARCHAR(80) NOT NULL,
    prefix VARCHAR(20) NOT NULL DEFAULT 'SJ',
    start_number INT NOT NULL DEFAULT 1001,
    next_number INT NOT NULL DEFAULT 1001,
    pad_width INT NOT NULL DEFAULT 4,
    skipped_numbers TEXT NULL,
    note VARCHAR(255) NULL,
    updated_by_user_id BIGINT UNSIGNED NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    PRIMARY KEY (sequence_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS number_sequence_log (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    sequence_key VARCHAR(80) NOT NULL,
    old_prefix VARCHAR(20) NULL,
    old_start_number INT NULL,
    old_next_number INT NULL,
    old_pad_width INT NULL,
    old_skipped_numbers TEXT NULL,
    new_prefix VARCHAR(20) NOT NULL,
    new_start_number INT NOT NULL,
    new_next_number INT NOT NULL,
    new_pad_width INT NOT NULL,
    new_skipped_numbers TEXT NULL,
    note VARCHAR(255) NULL,
    changed_by_user_id BIGINT UNSIGNED NULL,
    created_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    KEY idx_number_sequence_log_key (sequence_key, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO number_sequence_setting
    (sequence_key, prefix, start_number, next_number, pad_width, skipped_numbers, note, created_at, updated_at)
VALUES
    ('product_sku', 'SJ', 1001, 1001, 4, '[]', '商品 SKU 编号', NOW(), NOW())
ON DUPLICATE KEY UPDATE sequence_key=VALUES(sequence_key);

CREATE TABLE IF NOT EXISTS system_setting (
    setting_key VARCHAR(80) NOT NULL,
    setting_value LONGTEXT NOT NULL,
    note VARCHAR(255) NULL,
    updated_by_user_id BIGINT UNSIGNED NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    PRIMARY KEY (setting_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS system_setting_log (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    setting_key VARCHAR(80) NOT NULL,
    old_value LONGTEXT NULL,
    new_value LONGTEXT NOT NULL,
    changed_by_user_id BIGINT UNSIGNED NULL,
    created_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    KEY idx_system_setting_log_key (setting_key, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
