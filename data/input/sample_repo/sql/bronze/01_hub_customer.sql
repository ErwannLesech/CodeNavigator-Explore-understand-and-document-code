CREATE TABLE IF NOT EXISTS bronze.hub_customer (
    hk_customer CHAR(32) PRIMARY KEY,
    bk_customer_id VARCHAR(50) NOT NULL,
    load_dts TIMESTAMP NOT NULL,
    record_source VARCHAR(100) NOT NULL,
    CONSTRAINT uq_hub_customer_bk UNIQUE (bk_customer_id)
);

INSERT INTO bronze.hub_customer (hk_customer, bk_customer_id, load_dts, record_source)
SELECT DISTINCT
    MD5(CAST(src.customer_id AS TEXT)) AS hk_customer,
    CAST(src.customer_id AS VARCHAR(50)) AS bk_customer_id,
    CURRENT_TIMESTAMP AS load_dts,
    'crm.customer' AS record_source
FROM staging.customer_raw src
WHERE src.customer_id IS NOT NULL;
