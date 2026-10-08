"""
The agent itself — a controlled 3-step pipeline rather than a fully autonomous
LangChain agent:

    1. LLM turns the English question into SQL (given the schema context)
    2. The SQL is validated and executed against the read-only login
    3. The LLM turns the raw result rows into a plain-English answer

This is deliberately more explicit than a fully autonomous agent loop — it's
easier to debug, easier to explain in an interview, and easier to reason about
for safety, since each step's input/output is visible.
"""

import os
from dotenv import load_dotenv
from langchain.schema import SystemMessage, HumanMessage

from .schema_context import SCHEMA_CONTEXT
from .db import run_query, QueryExecutionError
from .guardrails import UnsafeQueryError

load_dotenv()

MAX_ROWS = int(os.environ.get("MAX_ROWS", "200"))
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "ollama").lower()


def _build_llm():
    if LLM_PROVIDER == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            api_key=os.environ["OPENAI_API_KEY"],
            model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            temperature=0,
        )
    # Default: Ollama — free, runs locally, no API key needed
    from langchain_ollama import ChatOllama
    return ChatOllama(
        model=os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:7b"),
        base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
        temperature=0,       # deterministic SQL generation, not creative
        num_ctx=8192,        # the schema description is long; Ollama's small default context would cut it off
        repeat_penalty=1.15, # discourages the model from looping/repeating tokens, which can otherwise abort generation
    )


llm = _build_llm()


def _generate_sql(question: str, retry_context: str = "") -> str:
    system = SystemMessage(content=SCHEMA_CONTEXT)
    user_prompt = (
        f"Write a single SQL Server SELECT query to answer this question:\n\n"
        f"{question}\n\n"
        f"{retry_context}"
        "Return ONLY the SQL query — no explanation, no markdown code fences."
    )
    response = llm.invoke([system, HumanMessage(content=user_prompt)])
    sql = response.content.strip()
    # strip accidental markdown fences if the model adds them anyway
    sql = sql.replace("```sql", "").replace("```", "").strip()
    return sql


def _summarize(question: str, columns: list, rows: list) -> str:
    preview_rows = rows[:20]  # cap what we send back to the LLM for summarizing
    table_preview = "\n".join(
        ", ".join(str(v) for v in row) for row in preview_rows
    )
    prompt = (
        f"The user asked: {question}\n\n"
        f"The query returned these columns: {columns}\n"
        f"And these rows (showing up to 20):\n{table_preview}\n\n"
        f"Total rows returned: {len(rows)}\n\n"
        "Write a short, direct answer in plain English. Include the specific "
        "numbers. If the result set is large, summarize the pattern rather than "
        "listing every row."
    )
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        return response.content.strip()
    except Exception as e:
        # The local model occasionally hits a generation error (e.g. a
        # repetition-loop abort) on this second call, even after the SQL
        # itself ran successfully. Rather than losing the result entirely,
        # fall back to showing the raw data plainly.
        fallback = (
            f"(The AI summary step failed: {e}. Showing raw results instead.)\n\n"
            f"Columns: {', '.join(columns)}\n"
        )
        fallback += "\n".join(", ".join(str(v) for v in row) for row in preview_rows)
        return fallback


def ask(question: str, max_retries: int = 2) -> dict:
    """
    Runs the full pipeline for one question. Returns a dict with the SQL used,
    the raw results, and the final natural-language answer — return all three
    so a demo can show the SQL, not just the answer (this is what makes it
    credible in an interview, rather than a black box).
    """
    retry_context = ""
    last_error = None

    for attempt in range(max_retries + 1):
        sql = _generate_sql(question, retry_context)
        try:
            columns, rows = run_query(sql)
            answer = _summarize(question, columns, rows)
            return {
                "question": question,
                "sql": sql,
                "columns": columns,
                "row_count": len(rows),
                "rows_preview": rows[:20],
                "answer": answer,
            }
        except (UnsafeQueryError, QueryExecutionError) as e:
            last_error = e
            retry_context = (
                f"Your previous SQL failed with this exact database error: {e}\n"
                "This usually means you referenced a column that does not exist "
                "directly on the table you queried. Re-read the schema above, "
                "particularly the 'COMMON MISTAKE TO AVOID' section, and check "
                "whether you need to JOIN dim_date (or another dimension table) "
                "to get the column you need, rather than assuming it exists on "
                "the fact table directly. Write a corrected query.\n\n"
            )

    return {
        "question": question,
        "sql": sql,
        "error": str(last_error),
        "answer": "I couldn't generate a working query for this question after "
                  "a few attempts. Try rephrasing it more specifically.",
    }
