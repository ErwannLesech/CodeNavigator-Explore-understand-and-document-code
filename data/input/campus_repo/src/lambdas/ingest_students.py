import json
import boto3
from datetime import datetime
from src.utils.aws_utils import RedshiftConnector, S3Handler
from src.utils.logging_utils import setup_logger

logger = setup_logger(__name__)

s3 = boto3.client("s3")
redshift_conn = RedshiftConnector()


def lambda_handler(event, context):
    bucket = event["Records"][0]["s3"]["bucket"]["name"]
    key = event["Records"][0]["s3"]["object"]["key"]

    try:
        logger.info(f"Processing students from {bucket}/{key}")

        s3_handler = S3Handler(bucket)
        students_data = s3_handler.read_json(key)

        with redshift_conn.get_connection() as conn:
            cursor = conn.cursor()

            for student in students_data:
                cursor.execute(
                    """
                    INSERT INTO staging.students (student_id, school_id, first_name, last_name, email, enrollment_date, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (student_id) DO UPDATE SET
                        first_name = EXCLUDED.first_name,
                        last_name = EXCLUDED.last_name,
                        email = EXCLUDED.email,
                        updated_at = %s
                    """,
                    (
                        student["student_id"],
                        student["school_id"],
                        student["first_name"],
                        student["last_name"],
                        student["email"],
                        student["enrollment_date"],
                        datetime.utcnow(),
                        datetime.utcnow(),
                    ),
                )

            conn.commit()
            logger.info(f"Successfully inserted {len(students_data)} students")

        return {
            "statusCode": 200,
            "body": json.dumps({"records_processed": len(students_data)}),
        }

    except Exception as e:
        logger.error(f"Error processing students: {str(e)}")
        raise
