import json
from pathlib import Path
report_path = Path('c:/Project rohan/Alpha_Lens/backend/win_rate_report.json')
with report_path.open('r', encoding='utf-8') as f:
    data = json.load(f)
stop_tickers = [trade['ticker'] for trade in data.get('trades', []) if trade.get('result') == 'STOP_HIT']
print('\n'.join(sorted(set(stop_tickers))))
print('COUNT:', len(stop_tickers))
