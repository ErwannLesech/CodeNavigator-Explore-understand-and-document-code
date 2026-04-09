CREATE TABLE IF NOT EXISTS silver.bv_order_enriched AS
WITH current_order AS (
    SELECT *
    FROM (
        SELECT
            s.hk_order,
            s.order_status,
            s.order_date,
            s.shipped_date,
            ROW_NUMBER() OVER (PARTITION BY s.hk_order ORDER BY s.load_dts DESC) AS rn
        FROM bronze.sat_order_status s
    ) x
    WHERE x.rn = 1
),
current_product AS (
    SELECT *
    FROM (
        SELECT
            s.hk_product,
            s.product_name,
            s.product_category,
            s.unit_price,
            ROW_NUMBER() OVER (PARTITION BY s.hk_product ORDER BY s.load_dts DESC) AS rn
        FROM bronze.sat_product_details s
    ) y
    WHERE y.rn = 1
)
SELECT
    l.hk_link_order_customer_product,
    l.hk_order,
    l.hk_customer,
    l.hk_product,
    ho.bk_order_id,
    hc.bk_customer_id,
    hp.bk_product_id,
    o.order_status,
    o.order_date,
    o.shipped_date,
    p.product_name,
    p.product_category,
    p.unit_price
FROM bronze.link_order_customer_product l
LEFT JOIN bronze.hub_order ho ON l.hk_order = ho.hk_order
LEFT JOIN bronze.hub_customer hc ON l.hk_customer = hc.hk_customer
LEFT JOIN bronze.hub_product hp ON l.hk_product = hp.hk_product
LEFT JOIN current_order o ON l.hk_order = o.hk_order
LEFT JOIN current_product p ON l.hk_product = p.hk_product;
