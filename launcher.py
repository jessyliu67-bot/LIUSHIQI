"""BIG BANG local one-click start and safe first-run data import.

Works offline for prepared resources. The application listens on loopback only.
Never publishes to a merchant account or modifies an old installation.
"""
from __future__ import annotations
import datetime as dt
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MARKER = ROOT / 'FIRST_RUN_IMPORT_AVAILABLE.marker'
RESOURCE = ROOT / 'resources' / 'BIG_BANG_V35_DUAL_600.zip'
PREFIX = 'BIG_BANG_V35'
EXPECTED_PATHS = None

def log(s):
    print('[BIG BANG] ' + s, flush=True)

def db_paths(database: Path):
    connection = sqlite3.connect(f'file:{database}?mode=ro', uri=True, timeout=5)
    try:
        result = [r[0] for r in connection.execute('SELECT inner_path FROM templates')]
        if len(result) != 300 or len(set(result)) != 300:
            raise RuntimeError('Existing database does not have exactly 300 unique template identities')
        return set(result)
    finally:
        connection.close()

def plausible_install(directory: Path):
    try:
        d=directory.resolve()
        if d == ROOT.resolve() or not (d/'app.py').is_file() or not (d/'data'/'bigbang.sqlite3').is_file():
            return False
        return db_paths(d/'data'/'bigbang.sqlite3') == db_paths(ROOT/'data'/'bigbang.sqlite3')
    except (OSError, sqlite3.Error, RuntimeError):
        return False

def find_previous():
    parent = ROOT.parent
    choices = []
    if plausible_install(parent):
        return [parent]
    try:
        children = list(parent.iterdir())
    except OSError:
        return []
    for p in children:
        if p.is_dir() and p != ROOT and plausible_install(p):
            choices.append(p)
    return choices

def select_old_folder():
    if os.name != 'nt':
        return None
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox
        root=tk.Tk();root.withdraw();root.attributes('-topmost',True)
        choose=messagebox.askyesno('BIG BANG - Import existing data',
            'Could not automatically find your previous BIG BANG installation next to this folder.\n\n'
            'To KEEP existing store/company/domain data, select Yes and choose your OLD BIG BANG folder once.\n\n'
            'Select No only if you want a clean 300-template workspace.',parent=root)
        selected=filedialog.askdirectory(title='Select your existing BIG BANG folder',parent=root) if choose else ''
        root.destroy()
        if selected:
            p=Path(selected)
            if not plausible_install(p):
                raise RuntimeError('Selected folder is not a compatible existing BIG BANG installation (300 template IDs required).')
            return p
    except ImportError:
        log('Windows folder picker is not available. Use the package in the same parent directory as your old BIG BANG installation to import automatically.')
    return None

def import_existing(old:Path):
    # Old program is read-only. In-progress state remains recoverable.
    log('Found compatible old installation at: ' + str(old))
    backups = ROOT / '_local_backups'
    backups.mkdir(exist_ok=True)
    stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d_%H%M%S')
    original=ROOT/'data'
    saved=backups/('clean_seed_'+stamp)
    temp=ROOT/('_import_stage_'+stamp)
    dest_env=ROOT/'.env'
    env_backup=backups/('original_env_'+stamp)
    had_env=dest_env.exists()
    if had_env:shutil.copy2(dest_env,env_backup)
    try:
        shutil.copytree(old/'data',temp,symlinks=True)
        if db_paths(temp/'bigbang.sqlite3') != db_paths(original/'bigbang.sqlite3'):
            raise RuntimeError('Imported database template mapping differs from the 300 V35 resource mapping')
        if (temp/'ASSET_MANIFEST.json').exists():
            previous=json.loads((temp/'ASSET_MANIFEST.json').read_text('utf-8'))
            if previous.get('version') not in ('BIG_BANG_V13','BIG_BANG_V23','BIG_BANG_V23_1','BIG_BANG_V35',None):
                raise RuntimeError('Unsupported previous resource manifest version: '+str(previous.get('version')))
        original.rename(saved)
        temp.rename(original)
        if not had_env and (old/'.env').is_file():
            shutil.copy2(old/'.env',dest_env)
        # Validate BEFORE marking the import successful.
        from db import init,init_v3
        from bootstrap_v16 import bootstrap
        init();init_v3();manifest=bootstrap()
        if manifest.get('version')!='BIG_BANG_V35':
            raise RuntimeError('V35 resource activation failed')
        (ROOT/'DATA_IMPORT_INFO.json').write_text(json.dumps({'source':str(old),'utc':stamp,'original_not_modified':True,'seed_backup':str(saved)},indent=2),encoding='utf-8')
        MARKER.unlink(missing_ok=True)
        log('Previous store records and credentials imported; original installation was not changed.')
    except Exception:
        # Close SQLite handles from migration/bootstrap before reverting.
        if temp.exists():shutil.rmtree(temp,ignore_errors=True)
        if saved.exists():
            if original.exists():shutil.rmtree(original,ignore_errors=True)
            saved.rename(original)
        if not had_env and dest_env.exists():dest_env.unlink()
        elif had_env and env_backup.exists():shutil.copy2(env_backup,dest_env)
        raise

def ensure_dependencies():
    names=('fastapi','uvicorn','httpx','bs4','fitz','docx','PIL','pytesseract','multipart')
    absent=[]
    for name in names:
        try:__import__(name)
        except ImportError:absent.append(name)
    if absent:
        log('Installing missing Python dependencies (Internet may be needed the first time): '+', '.join(absent))
        subprocess.run([sys.executable,'-m','pip','install','-r',str(ROOT/'requirements.txt')],check=True)

def port_available(port=8787):
    with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as sock:
        return sock.connect_ex(('127.0.0.1',port)) != 0

def run():
    if sys.version_info < (3,10):
        raise RuntimeError('Python 3.10 or later is required.')
    os.chdir(ROOT)
    from resource_archive import materialize_resource_archive
    materialize_resource_archive()
    if not RESOURCE.is_file():
        raise RuntimeError('Bundled V35 resource not found. Extract the complete ZIP, not just the BAT file.')
    if not port_available():
        raise RuntimeError('Port 8787 is already occupied. Please close your previous BIG BANG server before starting this version.')
    # First-run migration only. Do not overwrite data on later starts.
    if MARKER.is_file():
        candidates=find_previous()
        if len(candidates)==1:
            import_existing(candidates[0])
        elif len(candidates)>1:
            log('Multiple old installations found; select the correct folder.')
            chosen=select_old_folder()
            if chosen:import_existing(chosen)
            else:log('NO DATA IMPORT. This installation will use the clean seeded 300-template database.')
        else:
            chosen=select_old_folder()
            if chosen:import_existing(chosen)
            else:log('NO DATA IMPORT. This installation will use the clean seeded 300-template database.')
        MARKER.unlink(missing_ok=True)
    ensure_dependencies()
    from db import init, init_v3, db
    init();init_v3()
    from bootstrap_v16 import bootstrap
    manifest=bootstrap()
    with db() as c:
        n=c.execute('SELECT count(*) FROM templates').fetchone()[0]
        stores=c.execute('SELECT count(*) FROM stores').fetchone()[0]
    if n != 300 or stores != 300:
        raise RuntimeError(f'Database validation failed: {n} templates, {stores} stores')
    log(f'READY: {manifest["version"]} | {stores} store slots | 600 Shopify/SHOPLINE bundles | 6900 resources')
    # Setup writes a private .env only when it is missing, and prints the local login password once.
    subprocess.run([sys.executable,str(ROOT/'setup.py')],check=True)
    import uvicorn
    browser=subprocess.Popen([sys.executable,str(ROOT/'wait_for_app.py')],cwd=ROOT)
    log('Starting local dashboard at http://127.0.0.1:8787/')
    uvicorn.run('app:app',host='127.0.0.1',port=8787,log_level='warning',reload=False)

if __name__=='__main__':
    try:run()
    except KeyboardInterrupt:
        log('Stopped.')
    except Exception:
        traceback.print_exc()
        log('Startup stopped safely; old BIG BANG installation has not been modified.')
        sys.exit(1)
