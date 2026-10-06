"""Bounded continuation of sanitized calls at one journal snapshot, never raw data."""
import base64
import hmac
import json
import re
import time
from journal import number
from model_evidence import model_history

def session_page(j,session,cursor=None,limit=500):
    if not isinstance(session,str) or not re.fullmatch('[a-f0-9]{32}',session):raise ValueError('invalid_session')
    if not isinstance(limit,int) or isinstance(limit,bool) or not 1<=limit<=500:raise ValueError('invalid_page_size')
    at=time.time();offset=0;snapshot=None
    if cursor is not None:
        if not isinstance(cursor,str) or not 0<len(cursor)<=512:raise ValueError('invalid_cursor')
        try:
            raw=json.loads(base64.urlsafe_b64decode(cursor.encode('ascii')))
            if not isinstance(raw,list) or len(raw)!=4:raise ValueError('invalid_cursor')
            at,offset,snapshot,signature=raw
            if number(at) is None or not time.time()-30*86400<=at<=time.time()+1:raise ValueError('expired_cursor')
            if not isinstance(offset,int) or isinstance(offset,bool) or not 0<=offset<=20000:raise ValueError('invalid_cursor')
            if not isinstance(snapshot,str) or not re.fullmatch('[a-f0-9]{32}',snapshot):raise ValueError('invalid_cursor')
            expected=j.digest('session-page',[session,at,offset,snapshot])
            if not isinstance(signature,str) or not hmac.compare_digest(signature,expected):raise ValueError('invalid_cursor')
        except (ValueError,TypeError,UnicodeError):raise ValueError('invalid_cursor') from None
    rows=sorted(j.calls(session,as_of=at),key=lambda c:(c['startedAt'] or c['endedAt'] or 0,c['id']))
    # Retention, late finishes, reconciled models or conflicts may mutate old rows.
    # Reject continuation rather than silently shifting a prior page's evidence.
    observed=j.digest('session-page-snapshot',rows)
    if snapshot is not None and not hmac.compare_digest(snapshot,observed):raise ValueError('snapshot_changed_reopen')
    snapshot=observed
    page=rows[offset:offset+limit];end=offset+len(page);more=end<len(rows)
    def token(position):return base64.urlsafe_b64encode(json.dumps([at,position,snapshot,j.digest('session-page',[session,at,position,snapshot])],separators=(',',':')).encode()).decode()
    next_cursor=token(end) if more else None
    limited=j.db.execute('SELECT count(*) FROM observation WHERE session=? AND received>=? AND received<=?',(session,at-30*86400,at)).fetchone()[0]>20000
    current=token(offset)
    return {'sessionId':session,'calls':page,'truncated':more,'cursor':current,'nextCursor':next_cursor,
            'snapshotAt':at,'pageOffset':offset,'callCount':len(rows),'eventLimitReached':limited,
            'modelHistory':model_history(rows),'coverage':'observed calls in a fixed 30-day snapshot; retention and event limits apply; refresh for new events'}
