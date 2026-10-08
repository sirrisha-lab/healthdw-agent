"""
Guardrails applied to every piece of SQL before it touches the database.
These run regardless of what the LLM was asked to do — the point is that the
agent's *prompt* isn't the safety mechanism, this code is.
"""

import re

BLOCKED_KEYWORDS = [
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "EXEC", "EXECUTE",
    "MERGE", "TRUNCATE", "GRANT", "REVOKE", "CREATE", "sp_", "xp_",
]


class UnsafeQueryError(Exception):
    """Raised when generated SQL fails a safety check."""
    pass


def validate_sql(sql: str) -> str:
    """
    Validates that a generated SQL string is a safe, read-only SELECT.
    Returns the (possibly modified) SQL if valid, or raises UnsafeQueryError.
    """
    cleaned = sql.strip().rstrip(";")

    # Must start with SELECT (allowing a leading WITH for CTEs)
    first_word = cleaned.split(None, 1)[0].upper() if cleaned else ""
    if first_word not in ("SELECT", "WITH"):
        raise UnsafeQueryError(
            f"Query must start with SELECT or WITH — got '{first_word}'. Query: {sql}"
        )

    # Block dangerous keywords anywhere in the query (word-boundary match)
    upper_sql = cleaned.upper()
    for keyword in BLOCKED_KEYWORDS:
        if re.search(r"\b" + re.escape(keyword) + r"\b", upper_sql):
            raise UnsafeQueryError(f"Blocked keyword '{keyword}' found in generated SQL: {sql}")

    # Block multiple statements (stacked queries via semicolon)
    if ";" in cleaned:
        raise UnsafeQueryError(f"Multiple statements are not allowed: {sql}")

    # Enforce a row cap if the query doesn't already have TOP or OFFSET/FETCH
    if not re.search(r"\bTOP\s+\d+\b", upper_sql) and "OFFSET" not in upper_sql:
        # Insert TOP N right after SELECT (or after SELECT DISTINCT)
        cleaned = re.sub(
            r"^(SELECT\s+(DISTINCT\s+)?)",
            r"\1TOP 200 ",
            cleaned,
            count=1,
            flags=re.IGNORECASE,
        )

    return cleaned
