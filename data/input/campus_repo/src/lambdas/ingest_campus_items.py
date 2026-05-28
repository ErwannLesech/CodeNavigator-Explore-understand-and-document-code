import json
from datetime import datetime
from src.utils.aws_utils import RedshiftConnector, S3Handler
from src.utils.logging_utils import setup_logger

logger = setup_logger(__name__)


def lambda_handler(event, context):
    bucket = event["Records"][0]["s3"]["bucket"]["name"]
    key = event["Records"][0]["s3"]["object"]["key"]

    try:
        logger.info(f"Processing campus items from {bucket}/{key}")

        s3_handler = S3Handler(bucket)
        items_data = s3_handler.read_json(key)

        redshift_conn = RedshiftConnector()

        with redshift_conn.get_connection() as conn:
            cursor = conn.cursor()

            for item in items_data:
                cursor.execute(
                    """
                    INSERT INTO staging.campus_items (item_id, school_id, category, name, price, quantity_available, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (item_id) DO UPDATE SET
                        price = EXCLUDED.price,
                        quantity_available = EXCLUDED.quantity_available,
                        updated_at = %s
                    """,
                    (
                        item["item_id"],
                        item["school_id"],
                        item["category"],
                        item["name"],
                        item["price"],
                        item["quantity_available"],
                        datetime.utcnow(),
                        datetime.utcnow(),
                    ),
                )

            conn.commit()
            logger.info(f"Inserted {len(items_data)} campus items")

        return {
            "statusCode": 200,
            "body": json.dumps({"records_processed": len(items_data)}),
        }

    except Exception as e:
        logger.error(f"Error processing campus items: {str(e)}")
        raise
