import json
from pathlib import Path

base = Path('test_publications')
files = list(base.glob('**/*.json'))

print(f'Found {len(files)} JSON files:\n')
print(f"{'File':<50} {'Has xml?':<10} {'Size (KB)':<12} {'Keys'}")
print('='*120)

for f in files:
    data = json.load(open(f, encoding='utf-8'))
    has_xml = 'xml' in data
    size = f.stat().st_size / 1024
    keys = ', '.join(data.keys())
    
    rel_path = str(f.relative_to(base))
    print(f"{rel_path:<50} {str(has_xml):<10} {size:<12.1f} {keys}")
