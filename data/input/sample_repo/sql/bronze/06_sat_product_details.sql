CREATE TABLE IF NOT EXISTS bronze.sat_product_details (
    hk_product CHAR(32) NOT NULL,
    load_dts TIMESTAMP NOT NULL,
    hashdiff CHAR(32) NOT NULL,
    product_name VARCHAR(255),
    product_category VARCHAR(100),
    unit_price NUMERIC(12, 2),
    record_source VARCHAR(100) NOT NULL,
    CONSTRAINT pk_sat_product_details PRIMARY KEY (hk_product, load_dts)
);

INSERT INTO bronze.sat_product_details (
    hk_product,
    load_dts,
    hashdiff,
    product_name,
    product_category,
    unit_price,
    record_source
)
SELECT
    MD5(CAST(src.product_id AS TEXT)) AS hk_product,
    CURRENT_TIMESTAMP AS load_dts,
    MD5(
        COALESCE(src.product_name, '') || '|' ||
        COALESCE(src.product_category, '') || '|' ||
        COALESCE(CAST(src.unit_price AS TEXT), '')
    ) AS hashdiff,
    src.product_name,
    src.product_category,
    src.unit_price,
    'erp.product' AS record_source
FROM staging.product_raw src
WHERE src.product_id IS NOT NULL;
