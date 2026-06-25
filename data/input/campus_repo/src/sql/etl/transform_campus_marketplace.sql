DELETE FROM fact.marketplace_metrics
WHERE (student_id, item_id) IN (
    SELECT DISTINCT student_id, item_id FROM staging.marketplace_purchases
    WHERE purchase_date >= CURRENT_DATE - INTERVAL '7 days'
);

WITH purchase_aggregation AS (
    SELECT
        student_id,
        item_id,
        school_id,
        COUNT(*) as purchase_count,
        SUM(amount) as total_spent,
        AVG(amount) as avg_purchase_amount,
        MAX(purchase_date) as last_purchase_date,
        RANK() OVER (PARTITION BY school_id ORDER BY SUM(amount) DESC) as item_popularity_rank
    FROM staging.marketplace_purchases
    WHERE purchase_date >= CURRENT_DATE - INTERVAL '90 days'
    GROUP BY student_id, item_id, school_id
)
INSERT INTO fact.marketplace_metrics (student_id, item_id, school_id, purchase_count, total_spent, avg_purchase_amount, last_purchase_date, processed_at)
SELECT
    pa.student_id,
    pa.item_id,
    pa.school_id,
    pa.purchase_count,
    pa.total_spent,
    pa.avg_purchase_amount,
    pa.last_purchase_date,
    GETDATE()
FROM purchase_aggregation pa
WHERE pa.item_popularity_rank <= 100;

UPDATE staging.marketplace_purchases
SET created_at = GETDATE()
WHERE created_at IS NULL;
