CREATE TABLE IF NOT EXISTS bronze.link_order_customer_product (
    hk_link_order_customer_product CHAR(32) PRIMARY KEY,
    hk_order CHAR(32) NOT NULL,
    hk_customer CHAR(32) NOT NULL,
    hk_product CHAR(32) NOT NULL,
    load_dts TIMESTAMP NOT NULL,
    record_source VARCHAR(100) NOT NULL,
    CONSTRAINT uq_lnk_ocp UNIQUE (hk_order, hk_customer, hk_product)
);

INSERT INTO bronze.link_order_customer_product (
    hk_link_order_customer_product,
    hk_order,
    hk_customer,
    hk_product,
    load_dts,
    record_source
)
SELECT DISTINCT
    MD5(
        COALESCE(CAST(src.order_id AS TEXT), '') || '|' ||
        COALESCE(CAST(src.customer_id AS TEXT), '') || '|' ||
        COALESCE(CAST(src.product_id AS TEXT), '')
    ) AS hk_link_order_customer_product,
    MD5(CAST(src.order_id AS TEXT)) AS hk_order,
    MD5(CAST(src.customer_id AS TEXT)) AS hk_customer,
    MD5(CAST(src.product_id AS TEXT)) AS hk_product,
    CURRENT_TIMESTAMP AS load_dts,
    'oms.order_line' AS record_source
FROM staging.order_line_raw src
WHERE src.order_id IS NOT NULL
  AND src.customer_id IS NOT NULL
  AND src.product_id IS NOT NULL;
