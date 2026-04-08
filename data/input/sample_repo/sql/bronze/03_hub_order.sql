CREATE TABLE IF NOT EXISTS bronze.hub_order (
    hk_order CHAR(32) PRIMARY KEY,
    bk_order_id VARCHAR(50) NOT NULL,
    load_dts TIMESTAMP NOT NULL,
    record_source VARCHAR(100) NOT NULL,
    CONSTRAINT uq_hub_order_bk UNIQUE (bk_order_id)
);

INSERT INTO bronze.hub_order (hk_order, bk_order_id, load_dts, record_source)
SELECT DISTINCT
    MD5(CAST(src.order_id AS TEXT)) AS hk_order,
    CAST(src.order_id AS VARCHAR(50)) AS bk_order_id,
    CURRENT_TIMESTAMP AS load_dts,
    'oms.order' AS record_source
FROM staging.order_raw src
WHERE src.order_id IS NOT NULL;
