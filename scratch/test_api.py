import urllib.request, json

resp = urllib.request.urlopen('http://127.0.0.1:5000/api/news/all')
data = json.loads(resp.read())
print(f'Total articles from API: {len(data)}')
news_with_stocks = [d for d in data if d.get('affected_stocks')]
print(f'Articles WITH stock impacts: {len(news_with_stocks)}')
print()
for item in news_with_stocks[:10]:
    print(f"  [id={item['id']}] {len(item['affected_stocks'])} stocks | {item['headline'][:60]}")
    for s in item['affected_stocks']:
        print(f"       -> {s['ticker']} {s['impact']} score={s['confidence_score']} status={s['status']}")
