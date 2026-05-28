DELETE FROM staging.holiday_calendar
WHERE holiday_date < CURRENT_DATE - INTERVAL '2 years';

INSERT INTO staging.holiday_calendar (holiday_date, holiday_name, region, is_national)
WITH cte_fixed_holidays AS (
    SELECT DATE(YEAR(GETDATE()) || '-01-01') as hdate, 'New Year' as hname, 'FR' as region, TRUE as is_nat
    UNION ALL
    SELECT DATE(YEAR(GETDATE()) || '-05-01'), 'Labour Day', 'FR', TRUE
    UNION ALL
    SELECT DATE(YEAR(GETDATE()) || '-07-14'), 'Bastille Day', 'FR', TRUE
    UNION ALL
    SELECT DATE(YEAR(GETDATE()) || '-12-25'), 'Christmas', 'FR', TRUE
)
SELECT hdate, hname, region, is_nat
FROM cte_fixed_holidays
WHERE NOT EXISTS (
    SELECT 1 FROM staging.holiday_calendar hc
    WHERE hc.holiday_date = cte_fixed_holidays.hdate
);

UPDATE staging.holiday_calendar
SET created_at = GETDATE()
WHERE created_at IS NULL;
