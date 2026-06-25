CREATE SCHEMA IF NOT EXISTS fact;
CREATE SCHEMA IF NOT EXISTS dim;

CREATE TABLE IF NOT EXISTS dim.student_profiles (
    student_profile_id INT IDENTITY(1,1) PRIMARY KEY,
    student_id VARCHAR(20) NOT NULL,
    school_id VARCHAR(20) NOT NULL,
    last_activity_date DATE,
    academic_level VARCHAR(50),
    engagement_score NUMERIC(5, 2),
    profile_created_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT GETDATE(),
    UNIQUE (student_id, school_id)
);

CREATE TABLE IF NOT EXISTS dim.school_directory (
    school_id VARCHAR(20) PRIMARY KEY,
    campus_id VARCHAR(20),
    name VARCHAR(255),
    address VARCHAR(500),
    city VARCHAR(100),
    country VARCHAR(2),
    total_students INT DEFAULT 0,
    effective_from TIMESTAMP,
    effective_to TIMESTAMP,
    is_current BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS fact.student_grades_summary (
    student_id VARCHAR(20) NOT NULL,
    school_id VARCHAR(20) NOT NULL,
    avg_grade NUMERIC(4, 2),
    max_grade NUMERIC(4, 2),
    min_grade NUMERIC(4, 2),
    total_assessments INT,
    stddev_grade NUMERIC(5, 3),
    percentile_rank NUMERIC(5, 3),
    processed_at TIMESTAMP,
    PRIMARY KEY (student_id, school_id)
);

CREATE TABLE IF NOT EXISTS fact.marketplace_metrics (
    student_id VARCHAR(20) NOT NULL,
    item_id VARCHAR(20) NOT NULL,
    school_id VARCHAR(20) NOT NULL,
    purchase_count INT,
    total_spent NUMERIC(10, 2),
    avg_purchase_amount NUMERIC(10, 2),
    last_purchase_date DATE,
    processed_at TIMESTAMP,
    PRIMARY KEY (student_id, item_id)
);

CREATE TABLE IF NOT EXISTS fact.daily_campus_activity (
    activity_date DATE NOT NULL,
    school_id VARCHAR(20) NOT NULL,
    active_students INT,
    total_purchases INT,
    total_revenue NUMERIC(12, 2),
    avg_purchase_value NUMERIC(10, 2),
    processed_at TIMESTAMP,
    PRIMARY KEY (activity_date, school_id)
);

CREATE INDEX idx_dim_student_profiles_school ON dim.student_profiles(school_id);
CREATE INDEX idx_fact_grades_school ON fact.student_grades_summary(school_id);
CREATE INDEX idx_fact_marketplace_school ON fact.marketplace_metrics(school_id);
