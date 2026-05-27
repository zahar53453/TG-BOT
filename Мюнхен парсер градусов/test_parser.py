import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'C:\Users\artem\OneDrive\Рабочий стол\5-минутный сканер')

from mingaweda_fetcher import _parse_html
from mingaweda_formatter import build_mingaweda_message
import urllib.request

req = urllib.request.Request('https://www.mingaweda.de/', headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req) as r:
    html = r.read().decode('iso-8859-1')

data = _parse_html(html)
if data:
    print('=== TELEGRAM MESSAGE PREVIEW ===')
    print(build_mingaweda_message(data))
else:
    print('PARSE FAILED')
