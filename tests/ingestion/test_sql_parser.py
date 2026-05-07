from src.ingestion.sql_parser import parse_sql_file


def test_parse_sql_file_extracts_schema_and_query() -> None:
    sql = """
CREATE TABLE users (
    id INT PRIMARY KEY,
    email TEXT NOT NULL
);

SELECT id, email FROM users;
"""

    result = parse_sql_file(source=sql, file_path="schema.sql", dialect="postgres")

    assert result.source_file == "schema.sql"
    assert len(result.schemas) == 1
    assert result.schemas[0].name == "users"
    assert any(col["name"] == "id" for col in result.schemas[0].columns)
    assert any(col["name"] == "email" for col in result.schemas[0].columns)

    assert len(result.queries) == 1
    query = result.queries[0]
    assert query.query_type == "SELECT"
    assert any(t.name == "users" for t in query.tables_read)


def test_parse_sql_file_extracts_ctas_lineage() -> None:
    sql = """
CREATE TABLE gold.sales_fact AS
SELECT customer_id, amount
FROM silver.orders;
"""

    result = parse_sql_file(source=sql, file_path="ctas.sql", dialect="postgres")

    assert len(result.queries) == 1
    query = result.queries[0]
    assert query.query_type == "CREATE"
    assert any(t.name == "sales_fact" for t in query.tables_written)
    assert any(t.name == "orders" for t in query.tables_read)


def test_parse_sql_file_extracts_insert_select_lineage() -> None:
    sql = """
INSERT INTO mart.customer_dim (customer_id)
SELECT id
FROM staging.customers;
"""

    result = parse_sql_file(source=sql, file_path="insert.sql", dialect="postgres")

    assert len(result.queries) == 1
    query = result.queries[0]
    assert query.query_type == "INSERT"
    assert any(t.name == "customer_dim" for t in query.tables_written)
    assert any(t.name == "customers" for t in query.tables_read)


def test_parse_sql_file_handles_sortkey_column_list_in_create_temp_table() -> None:
    sql = """
CREATE TEMP TABLE tmp_latest_addon
DISTSTYLE KEY
DISTKEY (booking__guest__res_package_hk)
SORTKEY (booking__guest__res_package_hk, lastchangeddate, snap_date)
AS
SELECT booking__guest__res_package_hk
FROM dv.link_booking__guest__res_package;
"""

    result = parse_sql_file(
        source=sql,
        file_path="redshift_create_temp.sql",
        dialect="redshift",
    )

    assert len(result.schemas) == 1
    assert result.schemas[0].name == "tmp_latest_addon"

    assert len(result.queries) == 1
    query = result.queries[0]
    assert query.query_type == "CREATE"
    assert any(t.name == "tmp_latest_addon" for t in query.tables_written)
    assert any(t.name == "link_booking__guest__res_package" for t in query.tables_read)


def test_parse_sql_file_extracts_ctas_columns() -> None:
    """Test that CREATE TABLE AS SELECT extracts column definitions from the SELECT."""
    sql = """
CREATE TABLE IF NOT EXISTS silver.bv_current_customer AS
WITH last_sat AS (
    SELECT
        s.hk_customer,
        s.customer_name,
        s.load_dts
    FROM bronze.sat_customer_profile s
)
SELECT
    h.hk_customer,
    h.bk_customer_id,
    l.customer_name,
    l.load_dts AS effective_dts
FROM bronze.hub_customer h
LEFT JOIN last_sat l
    ON h.hk_customer = l.hk_customer;
"""

    result = parse_sql_file(
        source=sql, file_path="ctas_with_cte.sql", dialect="postgres"
    )

    # Verify schema is extracted with columns
    assert len(result.schemas) == 1
    schema = result.schemas[0]
    assert schema.name == "bv_current_customer"

    # Verify all columns from the SELECT are extracted
    column_names = [col["name"] for col in schema.columns]
    assert "hk_customer" in column_names
    assert "bk_customer_id" in column_names
    assert "customer_name" in column_names
    assert "effective_dts" in column_names

    # Verify column types are unknown (expected for CTAS)
    for col in schema.columns:
        assert col["type"] == "UNKNOWN"
        assert col["nullable"] is True  # CTAS columns are typically nullable
        assert col["primary_key"] is False


def test_parse_sql_file_falls_back_when_dialect_mismatches() -> None:
    sql = """
CREATE TEMP TABLE tmp_latest_addon
DISTSTYLE KEY
DISTKEY (booking__guest__res_package_hk)
SORTKEY (booking__guest__res_package_hk, lastchangeddate, snap_date)
AS
SELECT booking__guest__res_package_hk
FROM dv.link_booking__guest__res_package;
"""

    result = parse_sql_file(
        source=sql,
        file_path="redshift_fallback.sql",
        dialect="mysql",
    )

    assert len(result.queries) == 1
    query = result.queries[0]
    assert query.query_type == "CREATE"
    assert any(t.name == "tmp_latest_addon" for t in query.tables_written)
