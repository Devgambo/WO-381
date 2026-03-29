import sys
import json
sys.path.append('.')
from main import _extract_missing_fields

with open('first_extract/initial_report_1774802809.md', 'r', encoding='utf-8') as f:
    content = f.read()

extracted = _extract_missing_fields(content)
with open('result.json', 'w', encoding='utf-8') as f:
    json.dump(extracted, f, indent=2)
