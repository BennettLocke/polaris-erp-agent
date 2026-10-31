-- Schema only. Apply explicitly; normal product reads must not install tables.
CREATE TABLE IF NOT EXISTS product_model_asset (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    oss_key VARCHAR(500) NOT NULL,
    url VARCHAR(1000) NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    byte_size BIGINT UNSIGNED NOT NULL,
    sha256 CHAR(64) NOT NULL,
    animation_count INT UNSIGNED NOT NULL DEFAULT 0,
    materials_json JSON NOT NULL,
    uploaded_by BIGINT UNSIGNED NOT NULL,
    origin_spu_id BIGINT UNSIGNED NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    deleted_at DATETIME NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_product_model_asset_oss_key (oss_key),
    KEY idx_product_model_asset_owner (uploaded_by, deleted_at),
    KEY idx_product_model_asset_origin (origin_spu_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS product_model_binding (
    spu_id BIGINT UNSIGNED NOT NULL,
    model_asset_id BIGINT UNSIGNED NOT NULL,
    model_config JSON NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    PRIMARY KEY (spu_id),
    UNIQUE KEY uk_product_model_binding_asset (model_asset_id),
    CONSTRAINT fk_product_model_binding_spu FOREIGN KEY (spu_id) REFERENCES product_spu (id),
    CONSTRAINT fk_product_model_binding_asset FOREIGN KEY (model_asset_id) REFERENCES product_model_asset (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
