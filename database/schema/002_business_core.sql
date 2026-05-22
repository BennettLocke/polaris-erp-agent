-- Business core schema owned by sjagent_core.
-- Covers customer/user/order/inventory flows approved for the first native migration.

CREATE TABLE IF NOT EXISTS party (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    name VARCHAR(160) NOT NULL,
    kind VARCHAR(20) NOT NULL DEFAULT 'customer',
    contact_name VARCHAR(80) NULL,
    phone VARCHAR(40) NULL,
    phone_normalized VARCHAR(40) NULL,
    address VARCHAR(300) NULL,
    wechat_name VARCHAR(120) NULL,
    auto_print_sales TINYINT NOT NULL DEFAULT 0,
    settlement_type VARCHAR(30) NULL,
    tags JSON NULL,
    note TEXT NULL,
    source VARCHAR(30) NOT NULL DEFAULT 'manual',
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    deleted_at DATETIME NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_party_phone_normalized (phone_normalized),
    KEY idx_party_name (name),
    KEY idx_party_kind (kind),
    KEY idx_party_phone (phone),
    KEY idx_party_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS auth_user (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    username VARCHAR(80) NOT NULL,
    password_hash VARCHAR(255) NULL,
    display_name VARCHAR(80) NOT NULL,
    phone VARCHAR(40) NULL,
    role VARCHAR(30) NOT NULL DEFAULT 'customer',
    linked_party_id BIGINT UNSIGNED NULL,
    approval_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    is_active TINYINT NOT NULL DEFAULT 1,
    is_admin TINYINT NOT NULL DEFAULT 0,
    last_login_at DATETIME NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_auth_user_username (username),
    KEY idx_auth_user_phone (phone),
    KEY idx_auth_user_party (linked_party_id),
    KEY idx_auth_user_role (role),
    KEY idx_auth_user_status (approval_status, is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS auth_identity (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id BIGINT UNSIGNED NOT NULL,
    provider VARCHAR(30) NOT NULL,
    external_user_id VARCHAR(160) NOT NULL,
    openid VARCHAR(160) NULL,
    unionid VARCHAR(160) NULL,
    raw_profile JSON NULL,
    is_enabled TINYINT NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_auth_identity_provider_external (provider, external_user_id),
    KEY idx_auth_identity_user (user_id),
    KEY idx_auth_identity_openid (openid),
    KEY idx_auth_identity_unionid (unionid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS auth_session (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id BIGINT UNSIGNED NOT NULL,
    token_hash CHAR(64) NOT NULL,
    client_type VARCHAR(30) NULL,
    ip VARCHAR(80) NULL,
    user_agent VARCHAR(500) NULL,
    expires_at DATETIME NOT NULL,
    revoked_at DATETIME NULL,
    created_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_auth_session_token_hash (token_hash),
    KEY idx_auth_session_user (user_id),
    KEY idx_auth_session_expires (expires_at),
    KEY idx_auth_session_revoked (revoked_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS warehouse (
    id BIGINT UNSIGNED NOT NULL,
    code VARCHAR(60) NOT NULL,
    name VARCHAR(120) NOT NULL,
    warehouse_type VARCHAR(30) NOT NULL DEFAULT 'main',
    address VARCHAR(300) NULL,
    contact_name VARCHAR(80) NULL,
    phone VARCHAR(40) NULL,
    is_default_sales TINYINT NOT NULL DEFAULT 0,
    is_default_inbound TINYINT NOT NULL DEFAULT 0,
    sort_order INT NULL,
    is_enabled TINYINT NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_warehouse_code (code),
    KEY idx_warehouse_name (name),
    KEY idx_warehouse_enabled (is_enabled)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO warehouse
    (id, code, name, warehouse_type, is_default_sales, is_default_inbound, sort_order, is_enabled, created_at, updated_at)
VALUES
    (1, 'self_store', '自己店里', 'store', 0, 0, 10, 1, NOW(), NOW()),
    (2, 'baixin', '百鑫仓库', 'main', 1, 1, 20, 1, NOW(), NOW())
ON DUPLICATE KEY UPDATE
    code=VALUES(code),
    name=VALUES(name),
    warehouse_type=VALUES(warehouse_type),
    is_default_sales=VALUES(is_default_sales),
    is_default_inbound=VALUES(is_default_inbound),
    sort_order=VALUES(sort_order),
    is_enabled=VALUES(is_enabled),
    updated_at=VALUES(updated_at);

CREATE TABLE IF NOT EXISTS workflow_order (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    workflow_no VARCHAR(80) NOT NULL,
    customer_id BIGINT UNSIGNED NULL,
    customer_name_snapshot VARCHAR(160) NOT NULL,
    customer_phone_snapshot VARCHAR(40) NULL,
    sku_id BIGINT UNSIGNED NULL,
    sku_no_snapshot VARCHAR(80) NULL,
    goods_name_snapshot VARCHAR(180) NOT NULL,
    color_snapshot VARCHAR(60) NULL,
    quantity DECIMAL(12,3) NOT NULL DEFAULT 0,
    unit_id BIGINT UNSIGNED NULL,
    order_type VARCHAR(40) NOT NULL DEFAULT 'other',
    order_image_urls JSON NULL,
    ocr_text TEXT NULL,
    is_screen_print TINYINT NOT NULL DEFAULT 0,
    is_made TINYINT NOT NULL DEFAULT 0,
    is_delivered TINYINT NOT NULL DEFAULT 0,
    sales_order_id BIGINT UNSIGNED NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'pending',
    remark TEXT NULL,
    source VARCHAR(30) NOT NULL DEFAULT 'manual',
    created_by_user_id BIGINT UNSIGNED NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    deleted_at DATETIME NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_workflow_order_no (workflow_no),
    KEY idx_workflow_order_customer (customer_id),
    KEY idx_workflow_order_sku (sku_id),
    KEY idx_workflow_order_sales (sales_order_id),
    KEY idx_workflow_order_status (status),
    KEY idx_workflow_order_flags (is_made, is_delivered)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS workflow_order_log (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    workflow_order_id BIGINT UNSIGNED NOT NULL,
    action VARCHAR(40) NOT NULL,
    field_name VARCHAR(80) NULL,
    old_value TEXT NULL,
    new_value TEXT NULL,
    operator_user_id BIGINT UNSIGNED NULL,
    note VARCHAR(500) NULL,
    created_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    KEY idx_workflow_order_log_order (workflow_order_id),
    KEY idx_workflow_order_log_action (action),
    KEY idx_workflow_order_log_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS sales_order (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    sales_no VARCHAR(80) NOT NULL,
    customer_id BIGINT UNSIGNED NOT NULL,
    customer_name_snapshot VARCHAR(160) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'draft',
    pay_type VARCHAR(30) NULL,
    pay_status VARCHAR(30) NOT NULL DEFAULT 'unpaid',
    total_quantity DECIMAL(12,3) NOT NULL DEFAULT 0,
    goods_amount DECIMAL(12,2) NOT NULL DEFAULT 0,
    discount_amount DECIMAL(12,2) NOT NULL DEFAULT 0,
    receivable_amount DECIMAL(12,2) NOT NULL DEFAULT 0,
    source VARCHAR(30) NOT NULL DEFAULT 'manual',
    source_workflow_id BIGINT UNSIGNED NULL,
    settlement_ledger_id BIGINT UNSIGNED NULL,
    settled_at DATETIME NULL,
    print_status VARCHAR(30) NOT NULL DEFAULT 'none',
    note TEXT NULL,
    created_by_user_id BIGINT UNSIGNED NULL,
    sales_at DATETIME NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    canceled_at DATETIME NULL,
    canceled_by_user_id BIGINT UNSIGNED NULL,
    cancel_reason VARCHAR(500) NULL,
    deleted_at DATETIME NULL,
    deleted_by_user_id BIGINT UNSIGNED NULL,
    delete_reason VARCHAR(500) NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_sales_order_no (sales_no),
    KEY idx_sales_order_customer (customer_id),
    KEY idx_sales_order_status (status),
    KEY idx_sales_order_sales_at (sales_at),
    KEY idx_sales_order_settlement (settlement_ledger_id),
    KEY idx_sales_order_canceled_by (canceled_by_user_id),
    KEY idx_sales_order_deleted_at (deleted_at),
    KEY idx_sales_order_deleted_by (deleted_by_user_id),
    KEY idx_sales_order_workflow (source_workflow_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS sales_order_item (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    sales_order_id BIGINT UNSIGNED NOT NULL,
    line_no INT NOT NULL,
    sku_id BIGINT UNSIGNED NOT NULL,
    sku_no_snapshot VARCHAR(80) NOT NULL,
    title_snapshot VARCHAR(180) NOT NULL,
    color_snapshot VARCHAR(60) NULL,
    warehouse_id BIGINT UNSIGNED NOT NULL,
    unit_id BIGINT UNSIGNED NOT NULL,
    quantity DECIMAL(12,3) NOT NULL,
    unit_price DECIMAL(12,2) NOT NULL,
    amount DECIMAL(12,2) NOT NULL,
    cost_price_snapshot DECIMAL(12,2) NULL,
    price_source VARCHAR(30) NULL,
    workflow_order_id BIGINT UNSIGNED NULL,
    note VARCHAR(500) NULL,
    created_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_sales_order_item_line (sales_order_id, line_no),
    KEY idx_sales_order_item_sku (sku_id),
    KEY idx_sales_order_item_warehouse (warehouse_id),
    KEY idx_sales_order_item_workflow (workflow_order_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS customer_balance_ledger (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    ledger_no VARCHAR(80) NOT NULL,
    customer_id BIGINT UNSIGNED NOT NULL,
    entry_type VARCHAR(30) NOT NULL,
    pay_type VARCHAR(30) NULL,
    amount DECIMAL(12,2) NOT NULL DEFAULT 0,
    applied_amount DECIMAL(12,2) NOT NULL DEFAULT 0,
    balance_delta DECIMAL(12,2) NOT NULL DEFAULT 0,
    related_month CHAR(7) NULL,
    note VARCHAR(500) NULL,
    created_by_user_id BIGINT UNSIGNED NULL,
    created_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_customer_balance_ledger_no (ledger_no),
    KEY idx_customer_balance_customer (customer_id),
    KEY idx_customer_balance_type (entry_type),
    KEY idx_customer_balance_month (related_month),
    KEY idx_customer_balance_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS print_template (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    template_key VARCHAR(80) NOT NULL,
    document_type VARCHAR(40) NOT NULL DEFAULT 'sales_order',
    name VARCHAR(120) NOT NULL,
    paper_size VARCHAR(20) NOT NULL DEFAULT 'A4',
    orientation VARCHAR(20) NOT NULL DEFAULT 'landscape',
    font_size INT NOT NULL DEFAULT 12,
    copies INT NOT NULL DEFAULT 1,
    show_logo TINYINT NOT NULL DEFAULT 0,
    show_operator TINYINT NOT NULL DEFAULT 1,
    show_customer_phone TINYINT NOT NULL DEFAULT 1,
    show_payment TINYINT NOT NULL DEFAULT 1,
    show_note TINYINT NOT NULL DEFAULT 1,
    header_text VARCHAR(200) NOT NULL DEFAULT '肆计包装销售单',
    footer_text VARCHAR(500) NULL,
    custom_css TEXT NULL,
    is_default TINYINT NOT NULL DEFAULT 1,
    is_enabled TINYINT NOT NULL DEFAULT 1,
    created_by_user_id BIGINT UNSIGNED NULL,
    updated_by_user_id BIGINT UNSIGNED NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_print_template_key (template_key),
    KEY idx_print_template_type (document_type, is_default, is_enabled)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO print_template
    (template_key, document_type, name, paper_size, orientation, font_size, copies,
     show_logo, show_operator, show_customer_phone, show_payment, show_note,
     header_text, footer_text, custom_css, is_default, is_enabled, created_at, updated_at)
VALUES
    ('sales_order_default', 'sales_order', '默认销售单模板', 'A5', 'landscape', 12, 1,
     0, 1, 1, 1, 1,
     '肆计包装销售单', '谢谢惠顾，请核对商品数量与金额。', '', 1, 1, NOW(), NOW())
ON DUPLICATE KEY UPDATE template_key=VALUES(template_key);

CREATE TABLE IF NOT EXISTS print_job (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    job_no VARCHAR(80) NOT NULL,
    document_type VARCHAR(40) NOT NULL DEFAULT 'sales_order',
    document_id BIGINT UNSIGNED NOT NULL,
    template_id BIGINT UNSIGNED NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'pending',
    print_url VARCHAR(300) NULL,
    copies INT NOT NULL DEFAULT 1,
    created_by_user_id BIGINT UNSIGNED NULL,
    printed_by_user_id BIGINT UNSIGNED NULL,
    created_at DATETIME NOT NULL,
    printed_at DATETIME NULL,
    updated_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_print_job_no (job_no),
    KEY idx_print_job_document (document_type, document_id),
    KEY idx_print_job_status (status, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS inventory_balance (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    sku_id BIGINT UNSIGNED NOT NULL,
    warehouse_id BIGINT UNSIGNED NOT NULL,
    unit_id BIGINT UNSIGNED NOT NULL,
    quantity DECIMAL(12,3) NOT NULL DEFAULT 0,
    reserved_qty DECIMAL(12,3) NOT NULL DEFAULT 0,
    available_qty DECIMAL(12,3) NOT NULL DEFAULT 0,
    low_stock_qty DECIMAL(12,3) NULL,
    last_ledger_id BIGINT UNSIGNED NULL,
    version BIGINT NOT NULL DEFAULT 0,
    updated_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_inventory_balance_sku_wh_unit (sku_id, warehouse_id, unit_id),
    KEY idx_inventory_balance_sku (sku_id),
    KEY idx_inventory_balance_warehouse (warehouse_id),
    KEY idx_inventory_balance_last_ledger (last_ledger_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS stock_document (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    doc_no VARCHAR(80) NOT NULL,
    doc_type VARCHAR(30) NOT NULL,
    direction VARCHAR(10) NOT NULL,
    warehouse_id BIGINT UNSIGNED NOT NULL,
    related_party_id BIGINT UNSIGNED NULL,
    related_sales_order_id BIGINT UNSIGNED NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'draft',
    total_quantity DECIMAL(12,3) NOT NULL DEFAULT 0,
    note TEXT NULL,
    created_by_user_id BIGINT UNSIGNED NULL,
    created_at DATETIME NOT NULL,
    confirmed_at DATETIME NULL,
    canceled_at DATETIME NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_stock_document_no (doc_no),
    KEY idx_stock_document_type (doc_type, direction),
    KEY idx_stock_document_warehouse (warehouse_id),
    KEY idx_stock_document_party (related_party_id),
    KEY idx_stock_document_sales (related_sales_order_id),
    KEY idx_stock_document_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS stock_document_item (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    stock_document_id BIGINT UNSIGNED NOT NULL,
    line_no INT NOT NULL,
    sku_id BIGINT UNSIGNED NOT NULL,
    sku_no_snapshot VARCHAR(80) NOT NULL,
    title_snapshot VARCHAR(180) NOT NULL,
    unit_id BIGINT UNSIGNED NOT NULL,
    quantity DECIMAL(12,3) NOT NULL,
    unit_cost DECIMAL(12,2) NULL,
    amount DECIMAL(12,2) NULL,
    reason VARCHAR(200) NULL,
    ledger_id BIGINT UNSIGNED NULL,
    created_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_stock_document_item_line (stock_document_id, line_no),
    KEY idx_stock_document_item_sku (sku_id),
    KEY idx_stock_document_item_ledger (ledger_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS stocktake_order (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    stocktake_no VARCHAR(80) NOT NULL,
    warehouse_id BIGINT UNSIGNED NOT NULL,
    scope_type VARCHAR(30) NOT NULL DEFAULT 'all',
    scope_value JSON NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'draft',
    total_diff_qty DECIMAL(12,3) NOT NULL DEFAULT 0,
    note TEXT NULL,
    created_by_user_id BIGINT UNSIGNED NULL,
    created_at DATETIME NOT NULL,
    confirmed_at DATETIME NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_stocktake_order_no (stocktake_no),
    KEY idx_stocktake_order_warehouse (warehouse_id),
    KEY idx_stocktake_order_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS stocktake_item (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    stocktake_order_id BIGINT UNSIGNED NOT NULL,
    sku_id BIGINT UNSIGNED NOT NULL,
    unit_id BIGINT UNSIGNED NOT NULL,
    book_qty DECIMAL(12,3) NOT NULL DEFAULT 0,
    counted_qty DECIMAL(12,3) NOT NULL DEFAULT 0,
    diff_qty DECIMAL(12,3) NOT NULL DEFAULT 0,
    reason VARCHAR(200) NULL,
    ledger_id BIGINT UNSIGNED NULL,
    created_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    KEY idx_stocktake_item_order (stocktake_order_id),
    KEY idx_stocktake_item_sku (sku_id),
    KEY idx_stocktake_item_ledger (ledger_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS transfer_order (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    transfer_no VARCHAR(80) NOT NULL,
    from_warehouse_id BIGINT UNSIGNED NOT NULL,
    to_warehouse_id BIGINT UNSIGNED NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'draft',
    total_quantity DECIMAL(12,3) NOT NULL DEFAULT 0,
    note TEXT NULL,
    created_by_user_id BIGINT UNSIGNED NULL,
    created_at DATETIME NOT NULL,
    confirmed_at DATETIME NULL,
    canceled_at DATETIME NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_transfer_order_no (transfer_no),
    KEY idx_transfer_order_from_wh (from_warehouse_id),
    KEY idx_transfer_order_to_wh (to_warehouse_id),
    KEY idx_transfer_order_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS transfer_order_item (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    transfer_order_id BIGINT UNSIGNED NOT NULL,
    line_no INT NOT NULL,
    sku_id BIGINT UNSIGNED NOT NULL,
    sku_no_snapshot VARCHAR(80) NOT NULL,
    title_snapshot VARCHAR(180) NOT NULL,
    unit_id BIGINT UNSIGNED NOT NULL,
    quantity DECIMAL(12,3) NOT NULL,
    out_ledger_id BIGINT UNSIGNED NULL,
    in_ledger_id BIGINT UNSIGNED NULL,
    note VARCHAR(500) NULL,
    created_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_transfer_order_item_line (transfer_order_id, line_no),
    KEY idx_transfer_order_item_sku (sku_id),
    KEY idx_transfer_order_item_out_ledger (out_ledger_id),
    KEY idx_transfer_order_item_in_ledger (in_ledger_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS inventory_ledger (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    ledger_no VARCHAR(80) NOT NULL,
    sku_id BIGINT UNSIGNED NOT NULL,
    sku_no_snapshot VARCHAR(80) NOT NULL,
    warehouse_id BIGINT UNSIGNED NOT NULL,
    unit_id BIGINT UNSIGNED NOT NULL,
    change_qty DECIMAL(12,3) NOT NULL,
    before_qty DECIMAL(12,3) NOT NULL,
    after_qty DECIMAL(12,3) NOT NULL,
    biz_type VARCHAR(40) NOT NULL,
    biz_id BIGINT UNSIGNED NULL,
    biz_item_id BIGINT UNSIGNED NULL,
    counterparty_warehouse_id BIGINT UNSIGNED NULL,
    operator_user_id BIGINT UNSIGNED NULL,
    note VARCHAR(500) NULL,
    occurred_at DATETIME NOT NULL,
    created_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_inventory_ledger_no (ledger_no),
    KEY idx_inventory_ledger_sku (sku_id),
    KEY idx_inventory_ledger_warehouse (warehouse_id),
    KEY idx_inventory_ledger_biz (biz_type, biz_id),
    KEY idx_inventory_ledger_occurred (occurred_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
