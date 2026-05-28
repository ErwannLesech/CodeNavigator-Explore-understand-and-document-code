import json
from datetime import datetime
from src.utils.aws_utils import RedshiftConnector, S3Handler
from src.utils.logging_utils import setup_logger

logger = setup_logger(__name__)


def lambda_handler(event, context):
    bucket = event["Records"][0]["s3"]["bucket"]["name"]
    key = event["Records"][0]["s3"]["object"]["key"]

    try:
        logger.info(f"Processing schools from {bucket}/{key}")

        s3_handler = S3Handler(bucket)
        schools_data = s3_handler.read_json(key)

        redshift_conn = RedshiftConnector()

        with redshift_conn.get_connection() as conn:
            cursor = conn.cursor()

            for school in schools_data:
                cursor.execute(
                    """
                    INSERT INTO staging.schools (school_id, campus_id, name, address, city, country, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (school_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        address = EXCLUDED.address,
                        city = EXCLUDED.city,
                        updated_at = %s
                    """,
                    (
                        school["school_id"],
                        school.get("campus_id"),
                        school["name"],
                        school["address"],
                        school["city"],
                        school.get("country", "FR"),
                        datetime.utcnow(),
                        datetime.utcnow(),
                    ),
                )

            conn.commit()
            logger.info(f"Successfully processed {len(schools_data)} schools")

        return {
            "statusCode": 200,
            "body": json.dumps({"records_processed": len(schools_data)}),
        }

    except Exception as e:
        logger.error(f"Error processing schools: {str(e)}")
        raise
