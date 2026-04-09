CREATE TABLE IF NOT EXISTS bronze.hub_product (
    hk_product CHAR(32) PRIMARY KEY,
    bk_product_id VARCHAR(50) NOT NULL,
    load_dts TIMESTAMP NOT NULL,
    record_source VARCHAR(100) NOT NULL,
    CONSTRAINT uq_hub_product_bk UNIQUE (bk_product_id)
);

INSERT INTO bronze.hub_product (hk_product, bk_product_id, load_dts, record_source)
SELECT DISTINCT
    MD5(CAST(src.product_id AS TEXT)) AS hk_product,
    CAST(src.product_id AS VARCHAR(50)) AS bk_product_id,
    CURRENT_TIMESTAMP AS load_dts,
    'erp.product' AS record_source
FROM staging.product_raw src
WHERE src.product_id IS NOT NULL;
