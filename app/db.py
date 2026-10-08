"""
Database access layer. Connects using the dedicated ai_agent_reader login
(never your own admin credentials), runs SQL through the guardrails first,
and enforces a query timeout so a runaway query can't hang or overload the server.
"""

import os
import pyodbc
from dotenv import load_dotenv
from .guardrails import validate_sql, UnsafeQueryError

load_dotenv()

SQL_SERVER = os.environ["SQL_SERVER"]
SQL_DATABASE = os.environ["SQL_DATABASE"]
SQL_LOGIN = os.environ["SQL_LOGIN"]
SQL_PASSWORD = os.environ["SQL_PASSWORD"]
QUERY_TIMEOUT = int(os.environ.get("QUERY_TIMEOUT_SECONDS", "10"))


class QueryExecutionError(Exception):
    """Raised when the database rejects a query that passed our own guardrails
    (e.g. an invalid column/table name). Caught by the agent layer and fed
    back to the LLM as a correction signal, same as UnsafeQueryError."""
    pass


def get_connection():
    conn_str = (
        "DRIVER={ODBC Driver 17 for SQL Server};"
        f"SERVER={SQL_SERVER};"
        f"DATABASE={SQL_DATABASE};"
        f"UID={SQL_LOGIN};"
        f"PWD={SQL_PASSWORD};"
    )
    conn = pyodbc.connect(conn_str, timeout=QUERY_TIMEOUT)
    return conn


def run_query(sql: str):
    """
    Validates and executes a SQL SELECT statement, returning (columns, rows).
    Raises UnsafeQueryError if the query fails our guardrails, or
    QueryExecutionError if the database itself rejects the query (e.g. a
    wrong column name the LLM invented). Both are caught by the agent layer
    to trigger a retry with the error message fed back to the LLM.
    """
    safe_sql = validate_sql(sql)

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(f"SET LOCK_TIMEOUT {QUERY_TIMEOUT * 1000};")
        try:
            cursor.execute(safe_sql)
        except pyodbc.Error as e:
            raise QueryExecutionError(str(e)) from e
        columns = [col[0] for col in cursor.description]
        rows = cursor.fetchall()
        return columns, rows
    finally:
        conn.close()
