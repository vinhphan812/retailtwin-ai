#!/usr/bin/env python3
"""Check coverage thresholds and fail if below minimum."""
import xml.etree.ElementTree as ET
import sys

tree = ET.parse('coverage.xml')
cov = tree.getroot()
found = 0
hit = 0
for counter in cov.findall('.//counter'):
    if counter.get('type') == 'branch':
        found = int(counter.get('found', 0))
        hit = int(counter.get('hit', 0))
if found > 0:
    pct = (hit / found) * 100
    print(f'branch: {hit}/{found} = {pct:.1f}%')
    if pct < 75:
        print(f'ERROR: branch coverage {pct:.1f}% < 75% threshold')
        sys.exit(1)
    print('PASS: branch coverage >= 75%')
else:
    print('WARNING: no branch data found')
