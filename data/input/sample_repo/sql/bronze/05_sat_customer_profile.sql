CREATE TABLE IF NOT EXISTS bronze.sat_customer_profile (
    hk_customer CHAR(32) NOT NULL,
    load_dts TIMESTAMP NOT NULL,
    hashdiff CHAR(32) NOT NULL,
    customer_name VARCHAR(255),
    customer_email VARCHAR(255),
    customer_country VARCHAR(100),
    record_source VARCHAR(100) NOT NULL,
    CONSTRAINT pk_sat_customer_profile PRIMARY KEY (hk_customer, load_dts)
);

INSERT INTO bronze.sat_customer_profile (
    hk_customer,
    load_dts,
    hashdiff,
    customer_name,
    customer_email,
    customer_country,
    record_source
)
SELECT
    MD5(CAST(src.customer_id AS TEXT)) AS hk_customer,
    CURRENT_TIMESTAMP AS load_dts,
    MD5(
        COALESCE(src.customer_name, '') || '|' ||
        COALESCE(src.customer_email, '') || '|' ||
        COALESCE(src.customer_country, '')
    ) AS hashdiff,
    src.customer_name,
    src.customer_email,
    src.customer_country,
    'crm.customer' AS record_source
FROM staging.customer_raw src
WHERE src.customer_id IS NOT NULL;
