#!/usr/bin/env python3
from pathlib import Path
import shutil, sys
here=Path(__file__).resolve().parent
target=here/'data'/'smart_money_archive.jsonl'; target.parent.mkdir(exist_ok=True)
if target.exists():
 print(f'Archive already present: {target}'); sys.exit(0)
names=['ATLAS_SPOT_ALPHA_LAB_V1_ZEC','ATLAS_SPOT_ALPHA_LAB_V1','ATLAS_MULTI_ASSET_V4_2','ATLAS_MULTI_ASSET_V4_1']
for name in names:
 c=here.parent/name/'data'/'smart_money_archive.jsonl'
 if c.exists():
  shutil.copy2(c,target); print(f'Copied archive from {c} -> {target}'); sys.exit(0)
print('No previous archive found automatically. Collector may start a new archive.')
