"""Shared bounded CLI for journal, inventory and observational comparisons."""
import json
from pathlib import Path
from analytics import report, compare
from journal import Journal, atomic_json, atomic_text
from instrumentation import configure_hooks, scan_inventory
from evidence_pack import evidence_pack
from model_evidence import model_history
from session_view import session_page

def run(args):
    j=Journal(args.state)
    try:
        if args.action=='daily':
            from daily_review import daily_review, daily_markdown
            result=daily_review(j,getattr(args,'date',None),getattr(args,'utc_offset_minutes',0),args.provider)
            if getattr(args,'format','json')=='markdown':
                result=daily_markdown(result,args.language)
            if args.file:
                (atomic_text if isinstance(result,str) else atomic_json)(args.file,result)
                return {'saved':True,'localOnly':True}
            return result
        if args.action=='health':
            from collection_health import health
            return health(j)
        if args.action=='diagnostics':
            from diagnostics import diagnostic_report
            return diagnostic_report(j,day=getattr(args,'date',None),utc_offset_minutes=getattr(args,'utc_offset_minutes',0))
        if args.action=='backup':
            from collection_health import backup
            if not args.file:raise ValueError('backup_file_required')
            return backup(j,args.file)
        if args.action=='checks':
            from check_receipts import check_report
            return check_report(j)
        if args.action in {'asset','task','usage','check'}:
            metadata=getattr(args,'metadata',None)
            if metadata is not None:
                if args.file or len(metadata.encode())>65536:raise ValueError('invalid_metadata')
                spec=json.loads(metadata)
            else:
                if not args.file or args.file.is_symlink() or args.file.stat().st_size>65536:raise ValueError('invalid_metadata_file')
                spec=json.loads(args.file.read_text())
            if args.action=='check':
                from check_receipts import receipt
                return receipt(j,spec)
            from efficiency import register_asset,record_task,ingest_usage
            if args.action=='asset':return register_asset(j,spec)
            if args.action=='task':return record_task(j,spec)
            return ingest_usage(j,spec)
        if args.action=='compare-tasks':
            from efficiency import compare_tasks
            return compare_tasks(j,args.label,args.before,args.after,args.provider)
        if args.action=='widget-comparison':
            from efficiency import select_widget_comparison
            return select_widget_comparison(j,args.provider,args.label,args.before,args.after)
        if args.action=='review':
            from finding_review import review_finding
            return review_finding(j,args.finding,args.status,args.reason,args.days)
        if args.action=='report':
            r=report(j)
            if getattr(args,'format','json')=='markdown':
                from review_pack import markdown_pack
                return markdown_pack(r,args.language)
            return r
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
            trusted=getattr(args,'trusted_skills_dir',[])
            data=scan_inventory(args.provider,args.skills_dir,args.config,trusted)
            # Replace only this provider; preserve the peer's inventory.
            if getattr(args,'remember_sources',False):
                from inventory_refresh import remember_sources
                if not (args.skills_dir or args.config):raise ValueError('inventory_sources_required')
                # Refuse an invalid stored plan before changing the registry.
                from inventory_refresh import load_plans
                load_plans(j.state)
            from inventory_refresh import replace_provider
            replace_provider(j,args.provider,data)
            if getattr(args,'remember_sources',False):
                remember_sources(j,args.provider,args.skills_dir,args.config,trusted)
            return {'saved':True,'entries':len({(r['kind'],r['id']) for r in data}),'availability':'configured, not live verified',
                    'autoRefresh':bool(getattr(args,'remember_sources',False))}
        if args.action=='annotate':
            j.annotate(args.session,args.label,args.outcome,args.variant);return {'saved':True}
        if args.action=='declare':
            j.declare_capability(args.provider,args.session,args.capability,args.kind)
            return {'saved':True,'evidence':'manual declaration, not native invocation'}
        if args.action=='compare':return compare(j,args.label,args.before,args.after)
        if args.action=='export':
            if not args.file:raise ValueError('missing_file')
            if getattr(args,'format','json')=='markdown':
                from review_pack import markdown_pack
                atomic_text(args.file,markdown_pack(report(j),args.language))
            else:atomic_json(args.file,report(j))
            return {'saved':True,'localOnly':True}
        raise ValueError('invalid_action')
    finally:j.close()
