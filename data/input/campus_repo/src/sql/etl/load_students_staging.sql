WITH student_imports AS (
    SELECT
        student_id,
        school_id,
        first_name,
        last_name,
        email,
        enrollment_date,
        ROW_NUMBER() OVER (PARTITION BY student_id ORDER BY created_at DESC) as rn
    FROM staging.students
    WHERE created_at >= CURRENT_DATE - INTERVAL '1 day'
),
final_students AS (
    SELECT
        student_id,
        school_id,
        first_name,
        last_name,
        email,
        enrollment_date
    FROM student_imports
    WHERE rn = 1
)
INSERT INTO dim.student_profiles (student_id, school_id, profile_created_at, updated_at)
SELECT
    fs.student_id,
    fs.school_id,
    GETDATE(),
    GETDATE()
FROM final_students fs
WHERE NOT EXISTS (
    SELECT 1 FROM dim.student_profiles sp
    WHERE sp.student_id = fs.student_id AND sp.school_id = fs.school_id
);

UPDATE dim.student_profiles
SET updated_at = GETDATE()
WHERE student_id IN (
    SELECT DISTINCT student_id
    FROM staging.students
    WHERE updated_at >= CURRENT_DATE - INTERVAL '1 day'
);
