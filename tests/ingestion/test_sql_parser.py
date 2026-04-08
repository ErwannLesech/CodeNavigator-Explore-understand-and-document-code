from ingestion.sql_parser import parse_sql_file


def test_parse_sql_file_extracts_schema_and_query() -> None:
    sql = '''
CREATE TABLE users (
    id INT PRIMARY KEY,
    email TEXT NOT NULL
);

SELECT id, email FROM users;
'''

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
