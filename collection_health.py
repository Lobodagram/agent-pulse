"""Health and verified snapshots of Pulse's own sanitized journal, never native DBs."""
import os
from pathlib import Path
import sqlite3
import tempfile
import time

def health(j):
    from journal import MAX_EVENTS
    events=j.db.execute('SELECT count(*) FROM observation').fetchone()[0]
    check=j.db.execute('PRAGMA quick_check(1)').fetchone()
    counters={r['key']:{'count':r['value'],'supportedSince':r['started']} for r in j.db.execute('SELECT * FROM collection_counter')}
    return {'integrity':'ok' if check and check[0]=='ok' else 'failed',
            'retentionDays':30,'eventCap':MAX_EVENTS,'analysisEventLimit':MAX_EVENTS,
            'storedEvents':events,'analysisLimitReached':events>MAX_EVENTS,
            'storageBytes':j.stats()['bytes'],'retentionCounters':counters,
            'scope':'Pulse journal only; not native databases or full account coverage',
            'historicalDiscardCounts':'unknown before each counter supportedSince',
            'autoRepair':False}

def backup(j,destination):
    from journal import private_dir
    path=Path(destination)
    if not path.is_absolute() or path.exists() or path.is_symlink() or path.parent.is_symlink():raise ValueError('invalid_backup_destination')
    private_dir(path.parent)
    fd,name=tempfile.mkstemp(prefix='.pulse-backup-',dir=path.parent);os.close(fd)
    tmp=Path(name);target=None;started=time.monotonic()
    try:
        target=sqlite3.connect(tmp)
        def deadline(*_):
            if time.monotonic()-started>10:raise TimeoutError('backup_deadline')
        j.db.backup(target,pages=128,progress=deadline,sleep=.01)
        target.execute('CREATE TABLE IF NOT EXISTS backup_identity(fingerprint TEXT)')
        target.execute('DELETE FROM backup_identity')
        target.execute('INSERT INTO backup_identity VALUES (?)',(j.digest('backup-key',['journal']),))
        target.commit()
        checked=target.execute('PRAGMA quick_check(1)').fetchone()
        if not checked or checked[0]!='ok':raise ValueError('backup_integrity_failed')
        count=target.execute('SELECT count(*) FROM observation').fetchone()[0]
        target.close();target=None
        os.chmod(tmp,0o600)
        # Windows _commit requires a writable descriptor; the verified bytes
        # are unchanged, and publication still follows successful fsync.
        with tmp.open('r+b') as stream:os.fsync(stream.fileno())
        # Exclusive atomic publication: never replace an existing file, even
        # if it appeared after the validation above. Temporary file is same FS.
        os.link(tmp,path)
        return {'saved':True,'integrity':'ok','events':count,'includesCredentials':False,
                'scope':'sanitized journal snapshot; same local HMAC identity required for continued collection',
                'nativeDatabasesCopied':0,'restorePerformed':False}
    finally:
        if target is not None:target.close()
        tmp.unlink(missing_ok=True)
