WITH item_deduplication AS (
    SELECT
        item_id,
        school_id,
        category,
        name,
        price,
        quantity_available,
        ROW_NUMBER() OVER (PARTITION BY item_id ORDER BY updated_at DESC NULLS LAST) as rn
    FROM staging.campus_items
),
items_to_insert AS (
    SELECT
        id.item_id,
        id.school_id,
        id.category,
        id.name,
        id.price,
        id.quantity_available
    FROM item_deduplication id
    WHERE id.rn = 1
)
INSERT INTO fact.marketplace_metrics (item_id, school_id, purchase_count, total_spent, processed_at)
SELECT
    iti.item_id,
    iti.school_id,
    0,
    0.00,
    GETDATE()
FROM items_to_insert iti
WHERE NOT EXISTS (
    SELECT 1 FROM fact.marketplace_metrics fm
    WHERE fm.item_id = iti.item_id AND fm.school_id = iti.school_id
);

UPDATE staging.campus_items
SET updated_at = GETDATE()
WHERE updated_at IS NULL;
