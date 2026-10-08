-- Run in SSMS, connected as an admin (e.g. your Windows-authenticated account).
-- This creates a dedicated login the AI agent uses to connect — separate from
-- your own login, with read-only access and explicit writes/DDL denied.

-- Step 1: create the SQL login (change the password before running)
USE master;
GO
CREATE LOGIN ai_agent_reader WITH PASSWORD = 'ChangeThisStrongPassword!123';
GO

-- Step 2: create a matching user inside HealthDW and map it to the login
USE HealthDW;
GO
CREATE USER ai_agent_reader FOR LOGIN ai_agent_reader;
GO

-- Step 3: grant read-only access to the warehouse schema
GRANT SELECT ON SCHEMA::dbo TO ai_agent_reader;
GO

-- Step 4: explicitly deny writes and schema changes, as a second layer of
-- protection on top of only granting SELECT above. Belt and suspenders.
-- (Note: DROP is not a standalone permission in SQL Server — the ability to
-- drop an object is controlled by ALTER, which is already denied below.)
DENY INSERT, UPDATE, DELETE, ALTER, EXECUTE TO ai_agent_reader;
GO

-- Step 5 (recommended): do NOT grant this login any access to HealthDW_Staging
-- at all. The agent should only ever see the clean, analytics-ready star
-- schema — never the raw staging tables.

-- To verify the login truly cannot write, connect as ai_agent_reader and try:
--   INSERT INTO dim_province (province_key) VALUES (999);
-- It should fail with a permissions error.
