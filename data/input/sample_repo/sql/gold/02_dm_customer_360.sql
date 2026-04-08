CREATE TABLE IF NOT EXISTS gold.dm_customer_360 AS
SELECT
    c.bk_customer_id,
    c.customer_name,
    c.customer_email,
    c.customer_country,
    COUNT(f.bk_order_id) AS order_count,
    COALESCE(SUM(f.gross_amount), 0) AS lifetime_value
FROM silver.bv_current_customer c
LEFT JOIN gold.dm_sales_order_fact f
    ON c.bk_customer_id = f.bk_customer_id
GROUP BY
    c.bk_customer_id,
    c.customer_name,
    c.customer_email,
    c.customer_country;
