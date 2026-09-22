"""Durable, single-host storage. API and worker share this volume."""
import json
import os
import sqlite3
import uuid
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(os.environ.get('AEROVIEW_DATA', './data')).resolve()
ROOT.mkdir(parents=True, exist_ok=True)

def now():
    return datetime.now(timezone.utc).isoformat()

def uid():
    return str(uuid.uuid4())

def connect():
    db = sqlite3.connect(ROOT / 'survey.sqlite', timeout=30)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('PRAGMA foreign_keys=ON')
    return db

def init():
    with connect() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
          status TEXT NOT NULL, progress INTEGER NOT NULL, error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS layers(id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
          job_id TEXT NOT NULL REFERENCES jobs(id), metadata TEXT NOT NULL);
        ''')

def update_job(id, status, progress, error=None):
    with connect() as db:
        db.execute('UPDATE jobs SET status=?,progress=?,error=?,updated_at=? WHERE id=?',
                   (status, progress, error, now(), id))

def job_dir(id):
    # IDs reaching here originate in DB or server-generated UUIDs.
    return ROOT / 'jobs' / id

def save_layer(layer):
    with connect() as db:
        db.execute('INSERT INTO layers VALUES(?,?,?,?)',
                   (layer['id'], layer['projectId'], layer['jobId'], json.dumps(layer, allow_nan=False)))
