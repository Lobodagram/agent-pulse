"""Own opt-in provider keys; no native credential discovery or public output."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import time

@contextmanager
def secret_lock(directory):
    directory=Path(directory)
    if directory.is_symlink():raise ValueError('symlink_state')
    directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    path=directory/'.journal-key.lock'
    if path.is_symlink():raise ValueError('symlink_lock')
    with os.fdopen(os.open(path,os.O_RDWR|os.O_CREAT|getattr(os,'O_NOFOLLOW',0),0o600),'r+b') as lock:
        if os.name=='nt':
            import msvcrt
            deadline=time.monotonic()+.75
            while True:
                try:
                    lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);break
                except OSError:
                    if time.monotonic()>=deadline:raise
                    time.sleep(.01)
        else:
            import fcntl
            os.fchmod(lock.fileno(),0o600);fcntl.flock(lock,fcntl.LOCK_EX)
        try:yield
        finally:
            if os.name=='nt':
                lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(lock,fcntl.LOCK_UN)

def secrets(directory):
    path=Path(directory)/'Secrets.json'
    if not path.exists():return {}
    if path.is_symlink() or path.stat().st_size>65536:raise ValueError('invalid_secret_file')
    if os.name!='nt' and path.stat().st_mode & 0o077:raise ValueError('secret_permissions')
    value=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value,dict):raise ValueError('invalid_secret_file')
    return value

def save_key(directory,key,provider='glm',region='mainland-cn'):
    from providers import atomic_json
    if provider not in {'glm','kimi'}:raise ValueError('unsupported_key_provider')
    if region not in {'mainland-cn','global'}:raise ValueError('invalid_key_region')
    if not isinstance(key,str) or len(key)>4096:raise ValueError('invalid_key')
    key=key.strip()
    if any(c.isspace() for c in key):raise ValueError('invalid_key')
    # Same lock as journal initialization: preserve its HMAC and other providers.
    with secret_lock(directory):
        value=secrets(directory)
        if key:value[provider]={'api_key':key,**({'region':region} if provider=='kimi' else {})}
        else:value.pop(provider,None)
        atomic_json(Path(directory)/'Secrets.json',value)
    return {'saved':bool(key)}
