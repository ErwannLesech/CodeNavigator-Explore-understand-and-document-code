INSERT INTO dim.school_directory (school_id, campus_id, name, address, city, country, effective_from, is_current)
SELECT
    s.school_id,
    s.campus_id,
    s.name,
    s.address,
    s.city,
    s.country,
    GETDATE(),
    TRUE
FROM staging.schools s
WHERE NOT EXISTS (
    SELECT 1 FROM dim.school_directory sd
    WHERE sd.school_id = s.school_id AND sd.is_current = TRUE
);

UPDATE dim.school_directory sd
SET
    is_current = FALSE,
    effective_to = GETDATE()
WHERE
    is_current = TRUE
    AND school_id IN (
        SELECT DISTINCT school_id
        FROM staging.schools
        WHERE updated_at >= CURRENT_DATE - INTERVAL '1 day'
    );

UPDATE dim.school_directory
SET total_students = student_counts.cnt
FROM (
    SELECT school_id, COUNT(DISTINCT student_id) as cnt
    FROM dim.student_profiles
    GROUP BY school_id
) student_counts
WHERE dim.school_directory.school_id = student_counts.school_id
AND dim.school_directory.is_current = TRUE;
