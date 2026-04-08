CREATE TABLE IF NOT EXISTS bronze.sat_order_status (
    hk_order CHAR(32) NOT NULL,
    load_dts TIMESTAMP NOT NULL,
    hashdiff CHAR(32) NOT NULL,
    order_status VARCHAR(50),
    order_date DATE,
    shipped_date DATE,
    record_source VARCHAR(100) NOT NULL,
    CONSTRAINT pk_sat_order_status PRIMARY KEY (hk_order, load_dts)
);

INSERT INTO bronze.sat_order_status (
    hk_order,
    load_dts,
    hashdiff,
    order_status,
    order_date,
    shipped_date,
    record_source
)
SELECT
    MD5(CAST(src.order_id AS TEXT)) AS hk_order,
    CURRENT_TIMESTAMP AS load_dts,
    MD5(
        COALESCE(src.order_status, '') || '|' ||
        COALESCE(CAST(src.order_date AS TEXT), '') || '|' ||
        COALESCE(CAST(src.shipped_date AS TEXT), '')
    ) AS hashdiff,
    src.order_status,
    src.order_date,
    src.shipped_date,
    'oms.order' AS record_source
FROM staging.order_raw src
WHERE src.order_id IS NOT NULL;
