import os, sqlite3, uuid
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime, timezone
BASE=Path(__file__).resolve().parent
DATA=Path(os.getenv('BIGBANG_DATA_DIR',str(BASE/'data'))).resolve()
DATA.mkdir(parents=True,exist_ok=True)
(DATA/'uploads').mkdir(parents=True,exist_ok=True)
DB=DATA/'bigbang.sqlite3'

def uid(prefix): return prefix+'-'+uuid.uuid4().hex[:12].upper()
def now(): return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
@contextmanager
def db():
    c=sqlite3.connect(DB,timeout=25)
    c.row_factory=sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    c.execute('PRAGMA busy_timeout=25000')
    try:
        yield c
        c.commit()
    except:
        c.rollback(); raise
    finally: c.close()
def rows(cur):return [dict(x) for x in cur.fetchall()]
def row(cur):
    r=cur.fetchone();return dict(r) if r else None

def init():
    with db() as c:
        c.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS entities (
          id TEXT PRIMARY KEY, code TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
          registration_no TEXT DEFAULT '', country TEXT DEFAULT '', address TEXT DEFAULT '',
          phone TEXT DEFAULT '', email TEXT DEFAULT '', capacity INTEGER NOT NULL DEFAULT 0,
          status TEXT NOT NULL DEFAULT '待核验', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS entity_documents (
          id TEXT PRIMARY KEY, entity_id TEXT NOT NULL REFERENCES entities(id),
          filename TEXT NOT NULL, storage_name TEXT NOT NULL, byte_size INTEGER NOT NULL,
          content_type TEXT, uploaded_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS templates (
          id TEXT PRIMARY KEY, code TEXT NOT NULL UNIQUE, label TEXT NOT NULL,
          archive_name TEXT DEFAULT '', archive_path TEXT DEFAULT '', inner_path TEXT DEFAULT '',
          file_count INTEGER DEFAULT 0, checksum TEXT DEFAULT '', created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS stores (
          id TEXT PRIMARY KEY, code TEXT NOT NULL UNIQUE, label TEXT DEFAULT '',
          entity_id TEXT REFERENCES entities(id), template_id TEXT REFERENCES templates(id),
          status TEXT NOT NULL DEFAULT '待配置', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS store_domains (
          id TEXT PRIMARY KEY, store_id TEXT NOT NULL UNIQUE REFERENCES stores(id) ON DELETE CASCADE,
          domain TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS audits (
          id TEXT PRIMARY KEY, store_id TEXT NOT NULL REFERENCES stores(id),
          batch_id TEXT, mode TEXT NOT NULL DEFAULT 'rules', status TEXT NOT NULL DEFAULT '排队中',
          started_at TEXT, finished_at TEXT, summary_json TEXT DEFAULT '{}', error TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS audit_evidence (
          id TEXT PRIMARY KEY, audit_id TEXT NOT NULL REFERENCES audits(id),
          page_url TEXT NOT NULL, http_status INTEGER, content_hash TEXT DEFAULT '',
          excerpt TEXT DEFAULT '', checked_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS audit_issues (
          id TEXT PRIMARY KEY, audit_id TEXT NOT NULL REFERENCES audits(id),
          rule_code TEXT NOT NULL, severity TEXT NOT NULL, title TEXT NOT NULL,
          detail TEXT NOT NULL, page_url TEXT DEFAULT '', evidence_id TEXT REFERENCES audit_evidence(id),
          origin TEXT DEFAULT 'rule', state TEXT NOT NULL DEFAULT '待处理', created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_store_entity ON stores(entity_id);
        CREATE INDEX IF NOT EXISTS idx_audit_store ON audits(store_id);
        CREATE INDEX IF NOT EXISTS idx_issues_audit ON audit_issues(audit_id);
        ''')


def init_v3():
    """Non-destructive extension of V2.1. Existing 300 templates are untouched."""
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS store_contacts (
           store_id TEXT PRIMARY KEY REFERENCES stores(id) ON DELETE CASCADE,
           support_email TEXT NOT NULL DEFAULT '',
           email_status TEXT NOT NULL DEFAULT '未配置',
           updated_at TEXT NOT NULL
        );
        CREATE UNIQUE INDEX IF NOT EXISTS ux_contacts_email
          ON store_contacts(lower(support_email)) WHERE support_email<>'';
        CREATE TABLE IF NOT EXISTS intake_drafts (
           id TEXT PRIMARY KEY, filename TEXT NOT NULL, storage_name TEXT NOT NULL,
           method TEXT NOT NULL, extracted_json TEXT NOT NULL,
           status TEXT NOT NULL DEFAULT '待确认', created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS deployment_batches (
           id TEXT PRIMARY KEY, entity_id TEXT NOT NULL REFERENCES entities(id),
           store_ids_json TEXT NOT NULL, snapshot_json TEXT NOT NULL,
           created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS configuration_events (
           id TEXT PRIMARY KEY, batch_id TEXT, object_type TEXT NOT NULL,
           object_id TEXT NOT NULL, action TEXT NOT NULL,
           before_json TEXT, after_json TEXT, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS auto_allocation_proposals (
           id TEXT PRIMARY KEY, payload_json TEXT NOT NULL,
           status TEXT NOT NULL DEFAULT '待确认',
           created_at TEXT NOT NULL, expires_at TEXT NOT NULL,
           deployment_batch_id TEXT DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_auto_proposal_status ON auto_allocation_proposals(status,expires_at);
        CREATE INDEX IF NOT EXISTS idx_deploy_entity ON deployment_batches(entity_id);
        """)
