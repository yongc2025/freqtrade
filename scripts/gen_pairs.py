"""
    下载全量合约货币对
"""
import sys, json

pairs = json.load(sys.stdin)
lines = ['"pair_whitelist": [']
for p in sorted(pairs):
    escaped = p.encode('unicode_escape').decode('ascii')
    lines.append(f' "{escaped}",')
lines[-1] = lines[-1].rstrip(',')
lines.append(' ]')
with open('pair_whitelist.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
    
print(f'Done: {len(pairs)} pairs')