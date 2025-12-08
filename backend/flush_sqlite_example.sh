cd /workspaces/flash-reports-bc/backend
sqlite3 crimewatch.db <<'SQL'
DELETE FROM incidents_enriched;
DELETE FROM articles_raw;
DELETE FROM sources;
VACUUM;
SQL
