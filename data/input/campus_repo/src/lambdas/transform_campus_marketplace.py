import json
from datetime import datetime
from src.utils.aws_utils import RedshiftConnector
from src.utils.logging_utils import setup_logger

logger = setup_logger(__name__)


def lambda_handler(event, context):
    try:
        logger.info("Starting campus marketplace transformation")

        redshift_conn = RedshiftConnector()

        with redshift_conn.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                WITH purchase_history AS (
                    SELECT
                        student_id,
                        item_id,
                        school_id,
                        COUNT(*) as purchase_count,
                        SUM(amount) as total_spent,
                        MAX(purchase_date) as last_purchase_date,
                        AVG(amount) as avg_purchase_amount
                    FROM staging.marketplace_purchases
                    WHERE purchase_date >= CURRENT_DATE - INTERVAL '90 days'
                    GROUP BY student_id, item_id, school_id
                ),
                item_metrics AS (
                    SELECT
                        item_id,
                        school_id,
                        COUNT(DISTINCT student_id) as unique_buyers,
                        SUM(purchase_count) as total_purchases,
                        SUM(total_spent) as revenue,
                        RANK() OVER (PARTITION BY school_id ORDER BY SUM(total_spent) DESC) as item_rank
                    FROM purchase_history
                    GROUP BY item_id, school_id
                )
                INSERT INTO fact.marketplace_metrics (student_id, item_id, school_id, purchase_count, total_spent, avg_purchase_amount, last_purchase_date, processed_at)
                SELECT
                    ph.student_id,
                    ph.item_id,
                    ph.school_id,
                    ph.purchase_count,
                    ph.total_spent,
                    ph.avg_purchase_amount,
                    ph.last_purchase_date,
                    %s
                FROM purchase_history ph
                WHERE EXISTS (
                    SELECT 1 FROM item_metrics im
                    WHERE im.item_id = ph.item_id AND im.school_id = ph.school_id AND im.item_rank <= 50
                )
                ON CONFLICT (student_id, item_id) DO UPDATE SET
                    purchase_count = EXCLUDED.purchase_count,
                    total_spent = EXCLUDED.total_spent,
                    last_purchase_date = EXCLUDED.last_purchase_date,
                    processed_at = %s
            """,
                (datetime.utcnow(), datetime.utcnow()),
            )

            conn.commit()
            rows_affected = cursor.rowcount
            logger.info(f"Processed {rows_affected} marketplace transactions")

        return {
            "statusCode": 200,
            "body": json.dumps({"records_processed": rows_affected}),
        }

    except Exception as e:
        logger.error(f"Error transforming marketplace data: {str(e)}")
        raise
