"""
Deduplicate Supabase entries.
Keeps the row with the lowest id for each (date, start_time, end_time) group
and deletes all others.
"""
import json, os, sys

try:
    from supabase import create_client
except ImportError:
    sys.exit("supabase package not installed. Run: pip install supabase")

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
with open(CONFIG_PATH) as f:
    cfg = json.load(f)

url = cfg.get("supabase_url", "").strip()
key = cfg.get("supabase_key", "").strip()
if not url or not key:
    sys.exit("No Supabase credentials in config.json")

client = create_client(url, key)

print("Fetching all entries...")
rows = client.table("entries").select("id,sync_id,date,start_time,end_time,label").order("id").execute().data
print(f"  Total rows: {len(rows)}")

# Group by (date, start_time, end_time) — logical identity of a session
from collections import defaultdict
groups = defaultdict(list)
for r in rows:
    key_tuple = (r["date"], r["start_time"], r["end_time"])
    groups[key_tuple].append(r)

to_delete = []
for key_tuple, group in groups.items():
    if len(group) > 1:
        # Keep lowest id, delete the rest
        group.sort(key=lambda x: x["id"])
        dupes = group[1:]
        print(f"  Duplicate: {key_tuple} — keeping id={group[0]['id']}, deleting {[d['id'] for d in dupes]}")
        to_delete.extend(d["id"] for d in dupes)

if not to_delete:
    print("No duplicates found.")
    sys.exit(0)

print(f"\nDeleting {len(to_delete)} duplicate rows...")
for row_id in to_delete:
    client.table("entries").delete().eq("id", row_id).execute()
    print(f"  Deleted id={row_id}")

print(f"\nDone. Removed {len(to_delete)} duplicates.")
