CREATE TABLE IF NOT EXISTS silver.bv_current_customer AS
WITH last_sat AS (
    SELECT
        s.hk_customer,
        s.customer_name,
        s.customer_email,
        s.customer_country,
        s.load_dts,
        ROW_NUMBER() OVER (PARTITION BY s.hk_customer ORDER BY s.load_dts DESC) AS rn
    FROM bronze.sat_customer_profile s
)
SELECT
    h.hk_customer,
    h.bk_customer_id,
    l.customer_name,
    l.customer_email,
    l.customer_country,
    l.load_dts AS effective_dts
FROM bronze.hub_customer h
LEFT JOIN last_sat l
    ON h.hk_customer = l.hk_customer
   AND l.rn = 1;
