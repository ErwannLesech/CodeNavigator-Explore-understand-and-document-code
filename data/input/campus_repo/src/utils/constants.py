ENVIRONMENT = "dev"

S3_STAGING_BUCKET = "campus-platform-staging"
S3_ARCHIVE_BUCKET = "campus-platform-archive"

S3_PREFIXES = {
    "students": "staging/students/",
    "schools": "staging/schools/",
    "items": "staging/campus_items/",
    "purchases": "staging/marketplace/",
    "grades": "staging/grades/",
    "holidays": "staging/holidays/",
}

REDSHIFT_CLUSTER = "campus-prod-cluster"
REDSHIFT_DATABASE = "analytics"

STAGING_SCHEMA = "staging"
FACT_SCHEMA = "fact"
DIM_SCHEMA = "dim"

LOG_LEVEL = "INFO"
MAX_RETRIES = 3
RETRY_DELAY = 5

LAMBDA_TIMEOUT = 900

BATCH_SIZE = 1000
