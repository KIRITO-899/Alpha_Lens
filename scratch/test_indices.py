import urllib.request
import json

try:
    resp = urllib.request.urlopen("http://127.0.0.1:5000/api/indices", timeout=10)
    data = json.loads(resp.read())
    print(json.dumps(data, indent=2))
except Exception as e:
    print(f"ERROR: {e}")
