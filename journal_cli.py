"""Shared bounded CLI for journal, inventory and observational comparisons."""
import json
from pathlib import Path
from analytics import report, compare
from journal import Journal, atomic_json
from instrumentation import configure_hooks, scan_inventory
from evidence_pack import evidence_pack
from model_evidence import model_history
from session_view import session_page

def run(args):
    j=Journal(args.state)
    try:
        if args.action=='report':return report(j)
        if args.action=='evidence':
            result=evidence_pack(j,args.finding)
            if args.file:atomic_json(args.file,result);return {'saved':True,'localOnly':True}
            return result
        if args.action=='session':
            result=session_page(j,args.session,getattr(args,'cursor',None),getattr(args,'limit',500))
            if args.file:atomic_json(args.file,result);return {'saved':True,'localOnly':True,'nextCursor':result['nextCursor']}
            return result
        if args.action=='inventory':
            if not args.file or args.file.is_symlink() or args.file.stat().st_size>1024*1024:raise ValueError('invalid_inventory_file')
            j.import_inventory(json.loads(args.file.read_text()));return {'saved':True}
        if args.action=='scan':
            data=scan_inventory(args.provider,args.skills_dir,args.config)
            # Replace only this provider; preserve the peer's inventory.
            current=[dict(r) for r in j.db.execute('SELECT provider,id,kind,category,status,observed FROM inventory WHERE provider!=?',(args.provider,))]
            j.import_inventory(current+data);return {'saved':True,'entries':len(data),'availability':'configured, not live verified'}
        if args.action=='annotate':
            j.annotate(args.session,args.label,args.outcome,args.variant);return {'saved':True}
        if args.action=='declare':
            j.declare_capability(args.provider,args.session,args.capability,args.kind)
            return {'saved':True,'evidence':'manual declaration, not native invocation'}
        if args.action=='compare':return compare(j,args.label,args.before,args.after)
        if args.action=='export':
            if not args.file:raise ValueError('missing_file')
            atomic_json(args.file,report(j));return {'saved':True,'localOnly':True}
        raise ValueError('invalid_action')
    finally:j.close()
