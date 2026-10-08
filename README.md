# HealthDW Q&A Agent

A natural-language-to-SQL application built on top of a Canadian healthcare data warehouse.

The idea is simple: instead of writing SQL for every question, you can ask a question in plain English. The application uses a local Ollama model to generate the SQL, runs it against the warehouse, and returns the result. The generated SQL is also shown so the answer can be checked rather than treated as a black box.

## Safety design

Because the application allows an LLM to generate SQL, I added a few safeguards before allowing a query to run.

1. **Read-only SQL login** (`sql/create_readonly_login.sql`)  
   The application connects using `ai_agent_reader`, which has `SELECT` permission only. It cannot write to the database or run DDL statements, and it does not have access to `HealthDW_Staging`.

2. **SQL guardrails** (`app/guardrails.py`)  
   Every generated query is checked before it is sent to SQL Server. The query must start with `SELECT`, blocked keywords are rejected, stacked statements are not allowed, and a row limit is applied.

3. **Schema context** (`app/schema_context.py`)  
   The model is given a description of the warehouse tables and their join keys. This gives it the information it needs to build queries without allowing it to freely explore the database structure.

## Setup

### 1. Create the read-only SQL login

Open `sql/create_readonly_login.sql` in SSMS, replace the placeholder password, and run the script against your SQL Server instance.

### 2. Install Ollama and download the model

This project uses Ollama so the language model can run locally without an API key.

1. Download and install Ollama for Windows from [ollama.com](https://ollama.com).
2. Open Command Prompt and download the model:

```bash
ollama pull qwen2.5-coder:7b
```

3. Test that it is working:

```bash
ollama run qwen2.5-coder:7b "hello"
```

The 7B model needs roughly 8 GB of available RAM. A computer with 16 GB of total RAM should be more comfortable. If the model is too heavy for your machine, you can try `qwen2.5-coder:3b` and update `OLLAMA_MODEL` in `.env`.

### Optional: OpenAI

The application can also be configured to use OpenAI instead of Ollama. Set `LLM_PROVIDER=openai` in `.env` and add your `OPENAI_API_KEY`.

### 3. Configure the environment

Copy the example environment file:

```bash
copy .env.example .env
```

Keep `LLM_PROVIDER=ollama` if you want to use the local model, and add the password for the `ai_agent_reader` SQL login.

### 4. Install the Python dependencies

```bash
pip install -r requirements.txt
```

You will also need the **ODBC Driver 17 for SQL Server** installed on your machine if it is not already there.

### 5. Run the application

```bash
python -m app.main
```

Type `examples` to see the sample questions, or enter your own question.

## Example questions using the healthcare case study

The following questions are based on the healthcare data used in the existing case study. They are also useful for testing whether the agent can translate a natural-language question into SQL and return a result from the warehouse.

- "Which province had the longest 90th-percentile wait for knee replacement in 2024?"
  → The expected result is Manitoba, at about 726 days, matching the existing heat map.

- "What percentage of ED visits in Ontario resulted in hospital admission?"

- "Compare the median length of stay for admitted patients across all provinces."

- "Which province had the highest median length of stay for admitted patients?"

- "How did knee replacement wait times differ across provinces in 2024?"

- "Which province had the highest number of emergency department visits?"

## Questions you may be asked about this project

These are some of the technical questions that may come up when someone reviews the project.

### Why did you use a controlled workflow instead of a fully autonomous agent?

The application follows a clear sequence: generate SQL, validate it, execute it, and summarize the result. I chose this approach because it is easier to test and troubleshoot, and it gives me more control over what the model is allowed to do.

### How did you make the natural-language-to-SQL process safer?

I used several layers of protection. The database connection is read-only, every generated query goes through Python guardrails before it is executed, and the model receives a defined schema instead of having unrestricted access to the database structure.

### Why is the read-only database login important?

The Python guardrails are one layer of protection, but I did not want to rely on application code alone. The SQL login itself cannot perform writes or DDL operations. So even if a validation check were to fail, the database credentials still limit what the application can do.

### Why did you use Ollama?

I wanted to experiment with a local LLM rather than depending entirely on a hosted API. Ollama made it possible to run the model locally and test the natural-language-to-SQL workflow without requiring an API key.

### How does the agent know which tables and columns to use?

I provide the model with a hand-written schema description that explains the relevant tables and join keys. This gives the model some context about the warehouse when it generates the SQL.

### What happens if the generated SQL is wrong or unsafe?

The query is checked by the guardrail layer before it is executed. Queries that fail the checks are rejected. The application also has a retry so the model can try again when a query is rejected.

### What are the current limitations?

The local 7B model is not as accurate as a larger model on some complex SQL questions. There is currently no conversation memory, so each question is handled independently. The application also has only one retry, and the schema description has to be updated manually when new tables are added.

### What would you improve next?

If I continued developing this project, I would add query-result caching, a set of test questions with expected SQL and results, better logging and monitoring, and rate limiting. I would also test larger models and compare their SQL accuracy with the local model.

## Known limitations

- The local 7B model can produce incorrect SQL for more complicated questions. The generated SQL is displayed so it can be reviewed, and the guardrails check every query before execution.
- Each question is currently independent; there is no conversation memory.
- The application has one retry when a generated query is rejected.
- The schema context is maintained manually, so new warehouse tables need to be added to `app/schema_context.py`.
