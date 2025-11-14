#!/usr/bin/env python3
"""
Simple script to examine timestamps in the JSONS file
"""

import json

# Read first few lines to see the actual timestamp values
with open("2025-11-13_pleza.jsons", 'r') as f:
    for i, line in enumerate(f):
        if i >= 5:
            break
        line = line.strip()
        if line:
            try:
                data = json.loads(line)
                if 'timestamp' in data:
                    ts = data['timestamp']
                    print(f"Line {i+1}: timestamp = {ts}")
                    print(f"  Type: {type(ts)}")
                    print(f"  Length: {len(str(ts))} digits")
                    if i > 0:
                        prev_ts = prev_data['timestamp']
                        diff = ts - prev_ts
                        print(f"  Difference from previous: {diff}")
                prev_data = data
            except json.JSONDecodeError:
                print(f"Line {i+1}: Invalid JSON")