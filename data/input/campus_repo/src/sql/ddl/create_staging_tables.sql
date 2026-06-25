CREATE SCHEMA IF NOT EXISTS staging;

CREATE TABLE IF NOT EXISTS staging.students (
    student_id VARCHAR(20) PRIMARY KEY,
    school_id VARCHAR(20) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    email VARCHAR(255),
    enrollment_date DATE,
    created_at TIMESTAMP DEFAULT GETDATE(),
    updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS staging.schools (
    school_id VARCHAR(20) PRIMARY KEY,
    campus_id VARCHAR(20),
    name VARCHAR(255),
    address VARCHAR(500),
    city VARCHAR(100),
    country VARCHAR(2),
    created_at TIMESTAMP DEFAULT GETDATE(),
    updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS staging.campus_items (
    item_id VARCHAR(20) PRIMARY KEY,
    school_id VARCHAR(20) NOT NULL,
    category VARCHAR(100),
    name VARCHAR(255),
    price NUMERIC(10, 2),
    quantity_available INT,
    created_at TIMESTAMP DEFAULT GETDATE(),
    updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS staging.marketplace_purchases (
    purchase_id VARCHAR(30) PRIMARY KEY,
    student_id VARCHAR(20) NOT NULL,
    item_id VARCHAR(20) NOT NULL,
    school_id VARCHAR(20) NOT NULL,
    amount NUMERIC(10, 2),
    purchase_date DATE,
    created_at TIMESTAMP DEFAULT GETDATE()
);

CREATE TABLE IF NOT EXISTS staging.student_grades (
    grade_id VARCHAR(30) PRIMARY KEY,
    student_id VARCHAR(20) NOT NULL,
    school_id VARCHAR(20) NOT NULL,
    subject VARCHAR(100),
    grade_value NUMERIC(4, 2),
    grade_date DATE,
    created_at TIMESTAMP DEFAULT GETDATE()
);

CREATE TABLE IF NOT EXISTS staging.holiday_calendar (
    holiday_id INT IDENTITY(1,1) PRIMARY KEY,
    holiday_date DATE NOT NULL,
    holiday_name VARCHAR(255),
    region VARCHAR(50),
    is_national BOOLEAN,
    created_at TIMESTAMP DEFAULT GETDATE()
);

CREATE INDEX idx_staging_students_school ON staging.students(school_id);
CREATE INDEX idx_staging_purchases_student ON staging.marketplace_purchases(student_id);
CREATE INDEX idx_staging_grades_student ON staging.student_grades(student_id);
CREATE INDEX idx_staging_items_school ON staging.campus_items(school_id);
