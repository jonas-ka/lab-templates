"""`logbook`: the command line. Step one of the tooling: `check`, `schema`, `open-items`.
(`new`, `build`, `export`, `pull`, `migrate`, `cite`, `month` follow.)"""

from __future__ import annotations

import argparse
import os
import sys
from importlib import resources
from pathlib import Path

from . import __version__, check, state
from .book import open_book


def _cmd_check(a: argparse.Namespace) -> int:
    book = open_book(a.root)
    opts = check.Options(base=a.base, head=a.head, paths=[Path(p) for p in a.paths],
                         submitter=a.submitter, today=a.today, ci=a.ci)
    report = check.run(book, opts)
    print(report.to_json() if a.json else report.render(ci=a.ci))
    return report.exit_code


def _cmd_schema(a: argparse.Namespace) -> int:
    print(resources.files("lablogbook").joinpath("data/entry.schema.json").read_text(encoding="utf-8"))
    return 0


def _cmd_open(a: argparse.Namespace) -> int:
    book = open_book(a.root)
    st = state.compute(book.entries)
    items = st.open_items(book.entries)
    if a.project:
        items = [x for x in items if a.project in x[0].projects]
    for e, anchor, name in items:
        print(f"{e.date}  {name:5}  {e.id}#{anchor}  [{e.header.get('project')}] {e.header.get('title')}")
    print(f"{len(items)} open item(s)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="logbook", description="Log-book entries: format and checks.")
    ap.add_argument("--version", action="version", version=f"logbook {__version__}")
    ap.add_argument("--root", default=".", help="the log book (default: found from the current folder)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check", help="check entries before they are submitted")
    c.add_argument("paths", nargs="*", help="files to check (default: everything, or what --base changes)")
    c.add_argument("--base", help="git ref to compare with: check what HEAD changes (a pull request)")
    c.add_argument("--head", default="HEAD")
    c.add_argument("--submitter", default=os.environ.get("LOGBOOK_SUBMITTER"), help="GitHub login of whoever submits")
    c.add_argument("--today", help="YYYY-MM-DD (default: today)")
    c.add_argument("--ci", action="store_true", help="never print the text a finding matched")
    c.add_argument("--json", action="store_true")
    c.set_defaults(func=_cmd_check)

    s = sub.add_parser("schema", help="print the JSON Schema of the entry header")
    s.set_defaults(func=_cmd_schema)

    o = sub.add_parser("open-items", help="list issues and todos nothing has resolved yet")
    o.add_argument("--project")
    o.set_defaults(func=_cmd_open)

    a = ap.parse_args(argv)
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
