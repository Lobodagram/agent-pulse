"""Carry runtime notices into redistributable packages; fail if Python notice missing."""
from pathlib import Path
import argparse
import sys

def main():
    a=argparse.ArgumentParser();a.add_argument('destination');x=a.parse_args();out=Path(x.destination);out.mkdir(parents=True,exist_ok=True)
    roots=[Path(sys.base_prefix),Path(sys.prefix)]
    py=next((p for r in roots for name in ['LICENSE','LICENSE.txt'] if (p:=r/name).is_file()),None)
    if py is None:raise SystemExit('Python runtime license not found')
    (out/'PYTHON-LICENSE.txt').write_bytes(py.read_bytes())
    # Official Windows Python bundles Tcl/Tk notices beneath its tcl tree.
    for r in roots:
        for p in (r/'tcl').glob('*/license.terms'):
            (out/(p.parent.name+'-LICENSE.txt')).write_bytes(p.read_bytes())
    (out/'PYINSTALLER-NOTICE.txt').write_text('PyInstaller bootloader is GPL with its distribution exception. https://pyinstaller.org/en/stable/license.html\n')
if __name__=='__main__':main()
