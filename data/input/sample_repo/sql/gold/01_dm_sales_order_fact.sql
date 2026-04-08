CREATE TABLE IF NOT EXISTS gold.dm_sales_order_fact AS
SELECT
    e.bk_order_id,
    e.bk_customer_id,
    e.bk_product_id,
    e.order_date,
    e.shipped_date,
    e.order_status,
    e.product_category,
    COALESCE(e.unit_price, 0) AS unit_price,
    1 AS quantity,
    COALESCE(e.unit_price, 0) * 1 AS gross_amount
FROM silver.bv_order_enriched e;
