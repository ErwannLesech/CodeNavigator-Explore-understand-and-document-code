import json
from datetime import datetime
from src.utils.aws_utils import RedshiftConnector
from src.utils.logging_utils import setup_logger

logger = setup_logger(__name__)


def lambda_handler(event, context):
    try:
        logger.info("Starting student profile enrichment")

        redshift_conn = RedshiftConnector()

        with redshift_conn.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                WITH student_activity AS (
                    SELECT
                        s.student_id,
                        s.school_id,
                        COUNT(DISTINCT CASE WHEN mp.purchase_date >= CURRENT_DATE - INTERVAL '30 days' THEN mp.purchase_date END) as purchases_last_30days,
                        COUNT(DISTINCT CASE WHEN sg.grade_date >= CURRENT_DATE - INTERVAL '30 days' THEN sg.grade_date END) as assessments_last_30days,
                        MAX(CASE WHEN mp.purchase_date IS NOT NULL THEN mp.purchase_date END) as last_marketplace_activity,
                        CASE WHEN sgs.avg_grade >= 14 THEN 'excellent'
                             WHEN sgs.avg_grade >= 12 THEN 'good'
                             WHEN sgs.avg_grade >= 10 THEN 'average'
                             ELSE 'needs_improvement' END as academic_level
                    FROM staging.students s
                    LEFT JOIN staging.marketplace_purchases mp ON s.student_id = mp.student_id
                    LEFT JOIN staging.student_grades sg ON s.student_id = sg.student_id
                    LEFT JOIN fact.student_grades_summary sgs ON s.student_id = sgs.student_id
                    GROUP BY s.student_id, s.school_id, sgs.avg_grade
                ),
                engagement_score AS (
                    SELECT
                        student_id,
                        school_id,
                        (COALESCE(purchases_last_30days, 0) * 0.4 +
                         COALESCE(assessments_last_30days, 0) * 0.6) as engagement_score
                    FROM student_activity
                )
                UPDATE dim.student_profiles sp
                SET
                    last_activity_date = sa.last_marketplace_activity,
                    academic_level = sa.academic_level,
                    engagement_score = es.engagement_score,
                    updated_at = %s
                FROM student_activity sa
                JOIN engagement_score es ON sa.student_id = es.student_id
                WHERE sp.student_id = sa.student_id AND sp.school_id = sa.school_id
            """,
                (datetime.utcnow(),),
            )

            inserted = cursor.rowcount

            cursor.execute(
                """
                INSERT INTO dim.student_profiles (student_id, school_id, profile_created_at, updated_at)
                SELECT DISTINCT s.student_id, s.school_id, %s, %s
                FROM staging.students s
                WHERE NOT EXISTS (SELECT 1 FROM dim.student_profiles sp WHERE sp.student_id = s.student_id)
            """,
                (datetime.utcnow(), datetime.utcnow()),
            )

            conn.commit()
            total_affected = inserted + cursor.rowcount
            logger.info(f"Enriched {total_affected} student profiles")

        return {
            "statusCode": 200,
            "body": json.dumps({"records_processed": total_affected}),
        }

    except Exception as e:
        logger.error(f"Error enriching profiles: {str(e)}")
        raise
