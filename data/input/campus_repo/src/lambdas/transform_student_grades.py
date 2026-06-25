import json
from datetime import datetime
from src.utils.aws_utils import RedshiftConnector
from src.utils.logging_utils import setup_logger

logger = setup_logger(__name__)


def lambda_handler(event, context):
    try:
        logger.info("Starting student grades transformation")

        redshift_conn = RedshiftConnector()

        with redshift_conn.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                WITH grade_stats AS (
                    SELECT
                        student_id,
                        school_id,
                        AVG(grade_value) as avg_grade,
                        MAX(grade_value) as max_grade,
                        MIN(grade_value) as min_grade,
                        COUNT(*) as total_assessments,
                        STDDEV(grade_value) as stddev_grade
                    FROM staging.student_grades
                    WHERE grade_date >= CURRENT_DATE - INTERVAL '1 year'
                    GROUP BY student_id, school_id
                ),
                grade_ranking AS (
                    SELECT
                        student_id,
                        school_id,
                        avg_grade,
                        PERCENT_RANK() OVER (PARTITION BY school_id ORDER BY avg_grade) as percentile_rank
                    FROM grade_stats
                )
                INSERT INTO fact.student_grades_summary (student_id, school_id, avg_grade, max_grade, min_grade, total_assessments, percentile_rank, processed_at)
                SELECT
                    gs.student_id,
                    gs.school_id,
                    gs.avg_grade,
                    gs.max_grade,
                    gs.min_grade,
                    gs.total_assessments,
                    gr.percentile_rank,
                    %s
                FROM grade_stats gs
                LEFT JOIN grade_ranking gr ON gs.student_id = gr.student_id AND gs.school_id = gr.school_id
                ON CONFLICT (student_id) DO UPDATE SET
                    avg_grade = EXCLUDED.avg_grade,
                    percentile_rank = EXCLUDED.percentile_rank,
                    processed_at = %s
            """,
                (datetime.utcnow(), datetime.utcnow()),
            )

            conn.commit()
            rows_affected = cursor.rowcount
            logger.info(f"Transformed {rows_affected} student grade records")

        return {
            "statusCode": 200,
            "body": json.dumps({"records_processed": rows_affected}),
        }

    except Exception as e:
        logger.error(f"Error transforming student grades: {str(e)}")
        raise
