import urllib.request
import json

url = "https://alpha-lens-qvxw.onrender.com/api/debug-sql-runner"
headers = {
    "X-Alpha-Lens-Token": "alpha-lens-super-secret",
    "Content-Type": "application/json"
}

def run_sql(sql_query, params=()):
    data = json.dumps({"sql": sql_query, "params": params}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as res:
            return json.loads(res.read().decode("utf-8"))
    except Exception as e:
        print(f"Error executing SQL: {e}")
        if hasattr(e, 'read'):
            print(e.read().decode('utf-8'))
        return None

# Test 1: Check oldest news items in PostgreSQL news table
print("=== Oldest News in PG ===")
res = run_sql("SELECT id, headline, created_at FROM news ORDER BY id ASC LIMIT 10")
if res and res.get("status") == "success":
    for r in res.get("rows", []):
        print(r)

# Test 2: Check news items with ID between 100 and 1000
print("\n=== News count by ID range ===")
res = run_sql("SELECT COUNT(*) FROM news WHERE id < 3000")
if res and res.get("status") == "success":
    print("Under 3000:", res.get("rows")[0])

# Test 3: Check news count above 3000
res = run_sql("SELECT COUNT(*) FROM news WHERE id >= 3000")
if res and res.get("status") == "success":
    print("Above 3000:", res.get("rows")[0])

# Test 4: Check if there's any SQLite file still readable to verify its content
print("\n=== Inspect SQLite done file ===")
import sqlite3, os
# We can't access Render's file system directly from local python, but we can do it via SQL runner if we can attach or open it?
# Actually we can run a python command on the server if we add it, but first let's see why PG only has 106 rows.
