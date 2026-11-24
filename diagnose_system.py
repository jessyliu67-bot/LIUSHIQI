"""Offline diagnostics; runs without starting a browser."""
from __future__ import annotations
import json,os
from pathlib import Path
# Resolve optional custom BIGBANG_DATA_DIR from local .env before importing db.
_env_path=Path(__file__).resolve().parent/'.env'
if _env_path.is_file():
 for _line in _env_path.read_text(encoding='utf-8').splitlines():
  if '=' in _line and not _line.lstrip().startswith('#'):
   _k,_v=_line.split('=',1)
   if _k.strip()=='BIGBANG_DATA_DIR' and _v.strip():os.environ.setdefault('BIGBANG_DATA_DIR',_v.strip())
from db import init,init_v3
from readiness_api import local_diagnostics,source_scan
if __name__=='__main__':
 init();init_v3()
 print(json.dumps({'system':local_diagnostics(),'assets':source_scan()['summary']},ensure_ascii=False,indent=2))
