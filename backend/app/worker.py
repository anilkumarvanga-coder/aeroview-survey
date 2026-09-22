"""Single worker per data volume; each import runs in a bounded subprocess."""
import fcntl
import logging
import os
import subprocess
import sys
import time
from . import store

log = logging.getLogger('aeroview.worker')

def run_one():
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute("SELECT id FROM jobs WHERE status='queued' ORDER BY created_at LIMIT 1").fetchone()
        if row is None:
            return False
        id = row['id']
        db.execute("UPDATE jobs SET status='processing',updated_at=? WHERE id=?", (store.now(),id))
    try:
        subprocess.run([sys.executable, '-m', 'app.worker', '--process', id], check=True,
                       timeout=int(os.getenv('PROCESS_TIMEOUT_SECONDS','3600')))
    except (subprocess.SubprocessError, OSError):
        store.update_job(id, 'failed', 0, 'Processing timed out or worker failed. Inspect worker logs; re-upload to retry.')
    return True

def main():
    store.init()
    if len(sys.argv)==3 and sys.argv[1]=='--process':
        from .processing import process
        try:
            process(sys.argv[2])
        except Exception as exc:
            log.exception('Import failed')
            store.update_job(sys.argv[2], 'failed', 0, str(exc)[:1000])
        return
    with (store.ROOT / 'worker.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # A previous worker died. Partial products must never be reported as complete.
        with store.connect() as db:
            db.execute("UPDATE jobs SET status='failed',error='Worker interrupted; re-upload to retry.',updated_at=? WHERE status='processing'", (store.now(),))
        while True:
            if not run_one():
                time.sleep(2)

if __name__=='__main__':
    logging.basicConfig(level=logging.INFO)
    main()
