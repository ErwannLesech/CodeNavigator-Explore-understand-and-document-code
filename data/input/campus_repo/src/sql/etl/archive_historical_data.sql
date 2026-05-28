WITH archive_grades AS (
    SELECT
        grade_id,
        student_id,
        school_id,
        subject,
        grade_value,
        grade_date,
        created_at
    FROM staging.student_grades
    WHERE grade_date < CURRENT_DATE - INTERVAL '2 years'
),
archive_purchases AS (
    SELECT
        purchase_id,
        student_id,
        item_id,
        school_id,
        amount,
        purchase_date,
        created_at
    FROM staging.marketplace_purchases
    WHERE purchase_date < CURRENT_DATE - INTERVAL '2 years'
)
DELETE FROM staging.student_grades
WHERE grade_date < CURRENT_DATE - INTERVAL '2 years';

DELETE FROM staging.marketplace_purchases
WHERE purchase_date < CURRENT_DATE - INTERVAL '2 years';

UPDATE dim.student_profiles
SET updated_at = GETDATE()
WHERE updated_at < CURRENT_DATE - INTERVAL '90 days'
AND last_activity_date < CURRENT_DATE - INTERVAL '30 days';
