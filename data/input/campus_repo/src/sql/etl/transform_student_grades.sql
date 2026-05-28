WITH grade_aggregation AS (
    SELECT
        student_id,
        school_id,
        AVG(grade_value) as avg_grade,
        MAX(grade_value) as max_grade,
        MIN(grade_value) as min_grade,
        COUNT(*) as total_assessments,
        STDDEV(grade_value) as stddev_grade,
        PERCENT_RANK() OVER (PARTITION BY school_id ORDER BY AVG(grade_value)) as percentile_rank
    FROM staging.student_grades
    WHERE grade_date >= CURRENT_DATE - INTERVAL '1 year'
    GROUP BY student_id, school_id
),
grade_updates AS (
    SELECT
        ga.student_id,
        ga.school_id,
        ga.avg_grade,
        ga.max_grade,
        ga.min_grade,
        ga.total_assessments,
        ga.stddev_grade,
        ga.percentile_rank
    FROM grade_aggregation ga
)
DELETE FROM fact.student_grades_summary
WHERE (student_id, school_id) IN (
    SELECT DISTINCT student_id, school_id FROM staging.student_grades
    WHERE grade_date >= CURRENT_DATE - INTERVAL '7 days'
);

INSERT INTO fact.student_grades_summary (student_id, school_id, avg_grade, max_grade, min_grade, total_assessments, stddev_grade, percentile_rank, processed_at)
SELECT
    student_id,
    school_id,
    avg_grade,
    max_grade,
    min_grade,
    total_assessments,
    stddev_grade,
    percentile_rank,
    GETDATE()
FROM (
    SELECT
        student_id,
        school_id,
        AVG(grade_value) as avg_grade,
        MAX(grade_value) as max_grade,
        MIN(grade_value) as min_grade,
        COUNT(*) as total_assessments,
        STDDEV(grade_value) as stddev_grade,
        PERCENT_RANK() OVER (PARTITION BY school_id ORDER BY AVG(grade_value)) as percentile_rank
    FROM staging.student_grades
    WHERE grade_date >= CURRENT_DATE - INTERVAL '1 year'
    GROUP BY student_id, school_id
);
