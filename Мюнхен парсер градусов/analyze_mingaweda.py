import urllib.request
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

# Fetch the raw HTML
req = urllib.request.Request(
    'https://www.mingaweda.de/',
    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
)
with urllib.request.urlopen(req) as resp:
    html = resp.read().decode('utf-8', errors='replace')

print('=== PAGE LENGTH:', len(html))
print()

# Print raw HTML (save to file to avoid encoding issues)
with open('mingaweda_raw.html', 'w', encoding='utf-8') as f:
    f.write(html)
print('Raw HTML saved to mingaweda_raw.html')

# Find all <img src=...> and check for php endpoints
srcs = re.findall(r'src=["\']([^"\']+)["\']', html, re.IGNORECASE)
print('\n=== ALL SRC ATTRIBUTES ===')
for s in srcs:
    print(s)

# Find href links
hrefs = re.findall(r'href=["\']([^"\']+)["\']', html, re.IGNORECASE)
print('\n=== ALL HREF LINKS ===')
for h in hrefs:
    print(h)

# Search for data patterns - temperature, wind, etc.
# Look for numbers with degree signs or weather units
temp_vals = re.findall(r'[\d,\.\-]+\s*(?:&deg;|°|&#176;|Grad|km/h|hPa|mm|%|Bft)', html)
print('\n=== WEATHER VALUES FOUND ===')
for v in temp_vals[:30]:
    print(repr(v))

# Look for PHP data files
php_refs = re.findall(r'["\'/]([^"\'<> ]+\.php[^"\'<> ]*)["\']', html)
print('\n=== PHP FILE REFERENCES ===')
for p in php_refs[:20]:
    print(p)

# Look for any JavaScript variable assignments
js_vars = re.findall(r'(?:var|let|const)\s+\w+\s*=\s*["\'][^"\']+["\']', html)
print('\n=== JS VARIABLE ASSIGNMENTS ===')
for v in js_vars[:20]:
    print(v)

# Look for data= attributes
data_attrs = re.findall(r'data-\w+=["\'][^"\']+["\']', html)
print('\n=== DATA ATTRIBUTES ===')
for d in data_attrs[:20]:
    print(d)
