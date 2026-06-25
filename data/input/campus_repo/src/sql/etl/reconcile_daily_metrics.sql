WITH daily_activity_calc AS (
    SELECT
        CAST(mp.purchase_date AS DATE) as activity_date,
        mp.school_id,
        COUNT(DISTINCT mp.student_id) as active_students,
        COUNT(*) as total_purchases,
        SUM(mp.amount) as total_revenue,
        AVG(mp.amount) as avg_purchase_value
    FROM staging.marketplace_purchases mp
    GROUP BY CAST(mp.purchase_date AS DATE), mp.school_id
),
grade_activity AS (
    SELECT
        CAST(sg.grade_date AS DATE) as activity_date,
        sg.school_id,
        COUNT(DISTINCT sg.student_id) as assessed_students
    FROM staging.student_grades sg
    GROUP BY CAST(sg.grade_date AS DATE), sg.school_id
)
INSERT INTO fact.daily_campus_activity (activity_date, school_id, active_students, total_purchases, total_revenue, avg_purchase_value, processed_at)
SELECT
    dac.activity_date,
    dac.school_id,
    GREATEST(dac.active_students, COALESCE(ga.assessed_students, 0)) as active_students,
    dac.total_purchases,
    dac.total_revenue,
    dac.avg_purchase_value,
    GETDATE()
FROM daily_activity_calc dac
LEFT JOIN grade_activity ga ON dac.activity_date = ga.activity_date AND dac.school_id = ga.school_id
WHERE NOT EXISTS (
    SELECT 1 FROM fact.daily_campus_activity dca
    WHERE dca.activity_date = dac.activity_date AND dca.school_id = dac.school_id
);

DELETE FROM fact.daily_campus_activity
WHERE activity_date < CURRENT_DATE - INTERVAL '2 years';
