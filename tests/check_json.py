"""Validate every shipped JSON artifact, including duplicate keys and nonfinite values."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def reject_constant(value):
    raise ValueError(f'Invalid JSON constant: {value}')

def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'Duplicate JSON key: {key}')
        result[key] = value
    return result

if __name__ == '__main__':
    paths = [ROOT/'trend_data.json', ROOT/'etf_facts.json', ROOT/'valuation_cache.json', *sorted((ROOT/'detail_data').glob('*.json'))]
    for path in paths:
        json.loads(path.read_text(encoding='utf-8'), parse_constant=reject_constant, object_pairs_hook=unique_keys)
    print(f'Strict JSON passed: {len(paths)} files')
