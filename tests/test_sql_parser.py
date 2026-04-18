from sql_parser import SQLParser


def test_parse_simple_select_query():
    """SELECT is accepted; table extraction is driven by CREATE TABLE in this parser."""
    code = "SELECT id, name FROM users WHERE active = 1;"
    result = SQLParser().parse(code)

    assert result["language"] == "sql"
    assert result["summary"]["total_tables"] == 0
    assert result["tables"] == []


def test_parse_create_table_detects_table_and_columns():
    code = """
    CREATE TABLE orders (
        id INT PRIMARY KEY,
        total DECIMAL(10,2) NOT NULL
    );
    """
    result = SQLParser().parse(code)

    assert len(result["tables"]) == 1
    table = result["tables"][0]
    assert table["name"] == "orders"
    col_names = {c["name"] for c in table["columns"]}
    assert col_names == {"id", "total"}
    assert result["summary"]["total_tables"] == 1


def test_parse_empty_sql_input():
    result = SQLParser().parse("")

    assert result["language"] == "sql"
    assert result["tables"] == []
    assert result["relationships"] == []
    assert result["summary"]["total_tables"] == 0
