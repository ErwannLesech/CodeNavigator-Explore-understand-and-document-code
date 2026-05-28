import json
from src.utils.aws_utils import RedshiftConnector, S3Handler
from src.utils.logging_utils import setup_logger

logger = setup_logger(__name__)


def lambda_handler(event, context):
    bucket = event["Records"][0]["s3"]["bucket"]["name"]
    key = event["Records"][0]["s3"]["object"]["key"]

    try:
        logger.info(f"Processing holiday calendar from {bucket}/{key}")

        s3_handler = S3Handler(bucket)
        holidays_data = s3_handler.read_json(key)

        redshift_conn = RedshiftConnector()

        with redshift_conn.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("DELETE FROM staging.holiday_calendar")

            for holiday in holidays_data:
                cursor.execute(
                    """
                    INSERT INTO staging.holiday_calendar (holiday_date, holiday_name, region, is_national)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        holiday["date"],
                        holiday["name"],
                        holiday.get("region", "FR"),
                        holiday.get("is_national", True),
                    ),
                )

            conn.commit()
            logger.info(f"Loaded {len(holidays_data)} holiday dates")

        return {
            "statusCode": 200,
            "body": json.dumps({"records_processed": len(holidays_data)}),
        }

    except Exception as e:
        logger.error(f"Error processing holidays: {str(e)}")
        raise
