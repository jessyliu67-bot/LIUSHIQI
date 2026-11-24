"""Start the original BIG BANG application from the Windows launcher."""
from __future__ import annotations
import os, sys, sqlite3, shutil, secrets, json, datetime, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data'
os.chdir(ROOT)
os.environ['BIGBANG_DATA_DIR']=str(DATA)
os.environ['BIGBANG_DESKTOP_MODE']='1'

def template_identity(path):
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=8) as c:
        records=c.execute('SELECT id, code, inner_path FROM templates ORDER BY code').fetchall()
        return records

def import_previous():
    marker=ROOT/'desktop_initialized.json'
    if marker.exists():return
    seed=DATA/'bigbang.sqlite3'
    roots=[ROOT.parent/'V34_FINAL',ROOT.parent, ROOT.parent/'app', ROOT.parent/'original', ROOT.parent/'runtime', ROOT.parent/'BIG_BANG_FULL']
    # The launcher passes the directory of the downloaded executable as an additional exact location.
    if os.environ.get('BIGBANG_DOWNLOAD_DIR'):roots.append(Path(os.environ['BIGBANG_DOWNLOAD_DIR']))
    if os.environ.get('BIGBANG_DOWNLOAD_DIR'):roots.append(Path(os.environ['BIGBANG_DOWNLOAD_DIR'])/'BIG_BANG_FULL')
    choices=[];seen=set()
    for root in roots:
        root=root.resolve();old=root/'data'/'bigbang.sqlite3'
        if root==ROOT or root in seen or not (root/'app.py').is_file() or not old.is_file():continue
        seen.add(root)
        try:
            if template_identity(old)==template_identity(seed):choices.append(root)
        except Exception as ex: print('Previous workspace unavailable:',root,type(ex).__name__,flush=True)
    if len(choices)>1:
        # Only automatically prefer the known previous EXE's extraction root.
        canonical=ROOT.parent.resolve()
        if (ROOT.parent/'V34_FINAL').resolve() in choices:choices=[(ROOT.parent/'V34_FINAL').resolve()]
        elif canonical in choices:choices=[canonical]
        else:raise RuntimeError('Multiple compatible previous BIG BANG data folders found; no data was overwritten. See startup log.')
    if choices:
        old=choices[0];stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S');stage=ROOT/('_migration_'+stamp); backup=ROOT/('_clean_seed_'+stamp)
        print('Migrating compatible workspace:',old,flush=True)
        stage.mkdir();
        # Preserve uploaded business documents, reports, and any existing resource releases. Use SQLite backup for a consistent DB.
        for entry in (old/'data').iterdir():
            if entry.is_symlink() or entry.name in ('bigbang.sqlite3','bigbang.sqlite3-wal','bigbang.sqlite3-shm','bigbang.sqlite3-journal'):continue
            target=stage/entry.name
            if entry.is_dir():shutil.copytree(entry,target,ignore=shutil.ignore_patterns('*.tmp'),symlinks=False)
            elif entry.is_file():shutil.copy2(entry,target)
        source=sqlite3.connect((old/'data'/'bigbang.sqlite3').as_uri()+'?mode=ro',uri=True);dest=sqlite3.connect(stage/'bigbang.sqlite3')
        try:source.backup(dest)
        finally:source.close();dest.close()
        if template_identity(stage/'bigbang.sqlite3')!=template_identity(seed):raise RuntimeError('Old database has incompatible resource mapping.')
        if not (stage/'ASSET_MANIFEST.json').exists():shutil.copy2(DATA/'ASSET_MANIFEST.json',stage/'ASSET_MANIFEST.json')
        # Copy only known settings, never arbitrary environment overrides.
        values={}
        if (old/'.env').is_file():
            for line in (old/'.env').read_text('utf-8-sig').splitlines():
                key,sep,value=line.partition('=')
                if sep and key in ('DEEPSEEK_API_KEY','DEEPSEEK_MODEL','ADMIN_PASSWORD','SESSION_SECRET'):values[key]=value
        DATA.rename(backup);stage.rename(DATA)
        try:
            from db import init,init_v3
            from bootstrap_v16 import bootstrap
            init();init_v3();m=bootstrap();assert m['version']=='BIG_BANG_V35'
        except BaseException:
            failed=ROOT/('_failed_import_'+stamp);DATA.rename(failed);backup.rename(DATA);raise
        if values and not (ROOT/'.env').exists():
            (ROOT/'.env').write_text(''.join(k+'='+v+'\n' for k,v in values.items()),encoding='utf8')
        marker.write_text(json.dumps({'previous':str(old),'source_not_modified':True,'resource':'V35'},ensure_ascii=False),encoding='utf8')
    else:marker.write_text(json.dumps({'previous':None,'resource':'V35','clean_workspace':True}),encoding='utf8')

def configure():
    f=ROOT/'.env';vals={}
    if f.exists():
        for line in f.read_text('utf-8-sig').splitlines():
            k,s,v=line.partition('=')
            if s and k in ('DEEPSEEK_API_KEY','DEEPSEEK_MODEL','ADMIN_PASSWORD','SESSION_SECRET'):vals[k]=v
    if not vals.get('ADMIN_PASSWORD'):vals['ADMIN_PASSWORD']=secrets.token_urlsafe(18)
    if len(vals.get('SESSION_SECRET',''))<32:vals['SESSION_SECRET']=secrets.token_urlsafe(48)
    vals.setdefault('DEEPSEEK_API_KEY','');vals.setdefault('DEEPSEEK_MODEL','deepseek-flash')
    tmp=ROOT/'.env.new';tmp.write_text(''.join(k+'='+v+'\n' for k,v in vals.items()),encoding='utf8');os.replace(tmp,f)
    for k,v in vals.items():os.environ[k]=v

if __name__=='__main__':
    import_previous();configure()
    from db import init,init_v3
    init();init_v3()
    import uvicorn
    port=int(os.environ.get('BIGBANG_PORT','8787'))
    uvicorn.run('app:app',host='127.0.0.1',port=port,log_level='warning',access_log=False)
