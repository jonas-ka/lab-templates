"""`logbook`: the command line.

    logbook new --from draft.md            write an entry (a connected repository: submit it)
    logbook check [files] [--base REF]     check entries (what a pull request changes)
    logbook build [--pdf] [--html] [--single]
    logbook export [filters] --out f.pdf   a selection as a PDF (for someone outside the lab)
    logbook cite add <doi|isbn>            a reference into the reference list
    logbook pull                           the per-project copy of the central log book
    logbook migrate <logbook.typ>          a Typst log book into entries
    logbook month [--month YYYY-MM] --to DIR,  logbook digest
    logbook epics snapshot GROUP,  logbook epics restore ENTRY
    logbook init-github,  logbook from-issue N,  logbook open-items,  logbook schema
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from importlib import resources
from pathlib import Path

from . import __version__, check, state
from .book import open_book


def _yes(question: str) -> bool:
    try:
        return input(f"{question} [y/N] ").strip().lower() in ("y", "yes")
    except EOFError:
        return False


def _filter(a):
    from .selection import Filter
    split = lambda v: [y.strip() for x in (v or []) for y in x.split(",") if y.strip()]
    return Filter(projects=split(a.project), people=split(a.person), apparatus=split(a.apparatus), kinds=split(a.kind),
                  tags=split(a.tag), date_from=a.date_from, date_to=a.date_to, query=a.query, ids=split(a.id),
                  release_only=getattr(a, "release", False))


def _add_filters(p):
    p.add_argument("--project", action="append")
    p.add_argument("--person", action="append", help="handle")
    p.add_argument("--apparatus", action="append")
    p.add_argument("--kind", action="append")
    p.add_argument("--tag", action="append")
    p.add_argument("--from", dest="date_from", metavar="YYYY-MM-DD")
    p.add_argument("--to", dest="date_to", metavar="YYYY-MM-DD")
    p.add_argument("--query", help="words the entries must contain")
    p.add_argument("--id", action="append", help="entry id(s)")


# ------------------------------------------------------------------------------ commands -----
def _cmd_check(a) -> int:
    book = open_book(a.root)
    opts = check.Options(base=a.base, head=a.head, paths=[Path(p) for p in a.paths],
                         submitter=a.submitter, today=a.today, ci=a.ci)
    report = check.run(book, opts)
    print(report.to_json() if a.json else report.render(ci=a.ci))
    return report.exit_code


def _cmd_new(a) -> int:
    from . import connect, newentry
    header, body, base = {}, "", Path.cwd()
    if a.draft:
        d = Path(a.draft)
        if not d.is_file():
            print(f"logbook new: no draft at {d}", file=sys.stderr)
            return 1
        header, body = newentry.read_draft(d)
        base = d.resolve().parent
    for k in ("title", "project", "subproject", "kind"):
        if getattr(a, k):
            header[k] = getattr(a, k)
    for k, flag in (("tags", a.tag), ("apparatus", a.apparatus)):
        if flag:
            header[k] = list(dict.fromkeys(list(header.get(k) or []) + flag))
    if a.body is not None:
        body = sys.stdin.read() if a.body == "-" else a.body
    if a.body_file:
        body = Path(a.body_file).read_text(encoding="utf-8")
    try:
        t = connect.target(Path(a.root))
        if a.epics:
            import tempfile
            from . import epicsio
            snap = Path(tempfile.mkdtemp()) / f"{a.epics}-{dt.datetime.now():%Y-%m-%dT%H%M}.json"
            epicsio.snapshot(t.book, a.epics, snap, a.epics_label)
            header.setdefault("epics", []).append({"file": str(snap), "group": a.epics, **({"label": a.epics_label} if a.epics_label else {})})
        opts = newentry.Options(handle=a.as_handle, date=a.date, time=a.time, coauthors=a.coauthor or [],
                                interactive=sys.stdin.isatty() and not a.yes, confirm_export_control=a.confirm_export_control,
                                submit=not a.no_submit, dry_run=a.dry_run)
        return newentry.create(t, header, body, base, opts)
    except RuntimeError as e:   # ConnectError, NewError, EpicsError
        print(f"logbook new: {e}", file=sys.stderr)
        return 1


def _cmd_build(a) -> int:
    from . import render
    book = open_book(a.root)
    want_pdf = a.pdf is not None or not (a.html or a.single)
    try:
        if want_pdf:
            from . import pdf
            out = Path(a.pdf) if a.pdf else book.root / "build" / "logbook.pdf"
            print(f"PDF: {pdf.build(book, out)}")
        if a.html or a.single:
            from . import htmlview
            if a.html:
                print(f"HTML view: {htmlview.build(book, Path(a.html))}")
            if a.single:
                print(f"HTML view (one file): {htmlview.build(book, Path(a.single), single=True)}")
    except render.RenderError as e:
        print(f"logbook build: {e}", file=sys.stderr)
        return 1
    return 0


def _cmd_export(a) -> int:
    from . import render, reports
    if a.from_json:   # the export workflow's inputs
        inp = json.loads(a.from_json)
        for k in ("project", "person", "apparatus", "kind", "tag"):
            if inp.get(k):
                setattr(a, k, [inp[k]])
        a.date_from = inp.get("from") or a.date_from
        a.date_to = inp.get("to") or a.date_to
        a.query = inp.get("query") or a.query
        a.note = inp.get("note") or a.note
        a.anonymise = a.anonymise or str(inp.get("anonymise")).lower() == "true"
    book = open_book(a.root)
    try:
        path, n = reports.export(book, _filter(a), Path(a.out), a.requested_by, a.approved_by, a.note, a.anonymise)
    except render.RenderError as e:
        print(f"logbook export: {e}", file=sys.stderr)
        return 1
    if not path:
        print("no entries match: nothing exported", file=sys.stderr)
        return 1
    print(f"exported {n} entries: {path}")
    return 0


def _cmd_cite(a) -> int:
    from . import cite
    book = open_book(a.root)
    try:
        key, added = cite.add(book, a.ident)
    except cite.CiteError as e:
        print(f"logbook cite: {e}", file=sys.stderr)
        return 1
    print(f"{'added' if added else 'already in the list'}: [@{key}]  ({book.rel(book.bib_path)})")
    return 0


def _cmd_pull(a) -> int:
    from . import connect, projectcopy
    here, cfg = connect.local_config(Path(a.root))
    if not cfg.get("central"):
        print("logbook pull: this repository's logbook.yaml names no central log book (central: …)", file=sys.stderr)
        return 1
    try:
        dest = projectcopy.pull(here, cfg["central"], update=not a.no_update, out=sys.stdout)
    except RuntimeError as e:
        print(f"logbook pull: {e}", file=sys.stderr)
        return 1
    print(f"copy written: {dest} (read SUMMARY.md first)")
    return 0


def _cmd_migrate(a) -> int:
    from . import migrate
    book = open_book(a.into or a.root)
    mapping = dict(x.split("=", 1) for x in (a.author or []))
    try:
        r = migrate.migrate(Path(a.source), book, project=a.project, mapping=mapping,
                            confirm_export_control=a.confirm_export_control)
    except migrate.MigrateError as e:
        print(f"logbook migrate: {e}", file=sys.stderr)
        return 1
    print(r.render(book))
    return 1 if r.unknown_authors or r.missing_files else 0


def _cmd_month(a) -> int:
    from . import render, reports
    book = open_book(a.root)
    month = a.month or reports.previous_month(book.now().date())
    try:
        path, n = reports.month_pdf(book, month, Path(os.path.expanduser(a.to)))
    except render.RenderError as e:
        print(f"logbook month: {e}", file=sys.stderr)
        return 1
    print(f"{month}: {n} entries" + (f" -> {path}" if path else " (no PDF)"))
    return 0


def _cmd_digest(a) -> int:
    from . import reports
    print(reports.digest(open_book(a.root), a.today, a.days), end="")
    return 0


def _cmd_epics(a) -> int:
    from . import epicsio
    book = open_book(a.root)
    try:
        if a.action == "snapshot":
            out = Path(a.out or f"{a.target}-{dt.datetime.now():%Y-%m-%dT%H%M}.json")
            print(f"snapshot: {epicsio.snapshot(book, a.target, out, a.label)}")
            return 0
        for snap, _ in epicsio.stored(book, a.target, a.group):
            epicsio.restore(snap, (lambda q: True) if a.yes else _yes, sys.stdout)
        return 0
    except epicsio.EpicsError as e:
        print(f"logbook epics: {e}", file=sys.stderr)
        return 1


def _cmd_init_github(a) -> int:
    from . import github
    for rel in github.init_github(open_book(a.root), a.force):
        print(f"written: {rel}")
    return 0


def _cmd_from_issue(a) -> int:
    from . import github
    return github.from_issue(open_book(a.root), a.number, a.submitter, a.repo, sys.stdout)


def _cmd_copy_permissions(a) -> int:
    book = open_book(a.root)
    rows = [(n, str(p.get("copy_internal_until"))) for n, p in (book.projects or {}).items() if p.get("copy_internal_until")]
    if rows:
        print("Projects copied into internal repositories (readable by the whole organisation). Renew a date in "
              "projects.yaml to keep the permission, or leave it to lapse:\n")
        print("\n".join(f"- {n}: until {d}" for n, d in rows))
    return 0


def _cmd_schema(a) -> int:
    print(resources.files("lablogbook").joinpath("data/entry.schema.json").read_text(encoding="utf-8"))
    return 0


def _cmd_open(a) -> int:
    book = open_book(a.root)
    items = state.compute(book.entries).open_items(book.entries)
    if a.project:
        items = [x for x in items if a.project in x[0].projects]
    for e, anchor, name in items:
        print(f"{e.date}  {name:5}  {e.id}#{anchor}  [{e.header.get('project')}] {e.header.get('title')}")
    print(f"{len(items)} open item(s)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="logbook", description="Log-book entries: write, check, build, share.")
    ap.add_argument("--version", action="version", version=f"logbook {__version__}")
    ap.add_argument("--root", default=".", help="the log book or repository (default: found from the current folder)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    n = sub.add_parser("new", help="write an entry (from a draft or flags); in a connected repository, submit it")
    n.add_argument("--from", dest="draft", help="a draft: Markdown with a YAML header")
    n.add_argument("--title"); n.add_argument("--project"); n.add_argument("--subproject"); n.add_argument("--kind")
    n.add_argument("--tag", action="append"); n.add_argument("--apparatus", action="append")
    n.add_argument("--coauthor", action="append", help="handle of someone who took part")
    n.add_argument("--body", help="the text ('-': read it from stdin)"); n.add_argument("--body-file")
    n.add_argument("--date"); n.add_argument("--time", help="HH:MM")
    n.add_argument("--as", dest="as_handle", help="your handle (default: ~/.config/logbook/config.yaml, or your GitHub login)")
    n.add_argument("--epics", metavar="GROUP", help="store a snapshot of this PV group with the entry")
    n.add_argument("--epics-label")
    n.add_argument("--yes", action="store_true", help="ask nothing (co-authors are only proposed)")
    n.add_argument("--confirm-export-control", action="store_true", help="every attachment is free of export-controlled data")
    n.add_argument("--dry-run", action="store_true", help="check only: do not submit (connected) or keep (standalone)")
    n.add_argument("--no-submit", action="store_true")
    n.set_defaults(func=_cmd_new)

    c = sub.add_parser("check", help="check entries before they are submitted")
    c.add_argument("paths", nargs="*")
    c.add_argument("--base", help="git ref: check what HEAD changes relative to it (a pull request)")
    c.add_argument("--head", default="HEAD")
    c.add_argument("--submitter", default=os.environ.get("LOGBOOK_SUBMITTER"))
    c.add_argument("--today"); c.add_argument("--ci", action="store_true"); c.add_argument("--json", action="store_true")
    c.set_defaults(func=_cmd_check)

    b = sub.add_parser("build", help="the PDF (default build/logbook.pdf) and the HTML view")
    b.add_argument("--pdf", nargs="?", const=""); b.add_argument("--html"); b.add_argument("--single")
    b.set_defaults(func=_cmd_build)

    e = sub.add_parser("export", help="a selection of entries as a PDF")
    _add_filters(e)
    e.add_argument("--out", required=True); e.add_argument("--note"); e.add_argument("--requested-by"); e.add_argument("--approved-by")
    e.add_argument("--anonymise", action="store_true", help="authors by role, not by name")
    e.add_argument("--release", action="store_true", help="only entries marked release: candidate")
    e.add_argument("--from-json", help=argparse.SUPPRESS)
    e.set_defaults(func=_cmd_export)

    ci = sub.add_parser("cite", help="the reference list")
    cs = ci.add_subparsers(dest="action", required=True)
    ca = cs.add_parser("add", help="add a reference by DOI or ISBN")
    ca.add_argument("ident"); ca.set_defaults(func=_cmd_cite)

    p = sub.add_parser("pull", help="write this repository's copy of the central log book (logbook/)")
    p.add_argument("--no-update", action="store_true", help="do not pull the central clone first")
    p.set_defaults(func=_cmd_pull)

    m = sub.add_parser("migrate", help="a Typst log book into entries (nothing is committed)")
    m.add_argument("source"); m.add_argument("--project"); m.add_argument("--into", help="the log book to write into")
    m.add_argument("--author", action="append", metavar="NAME=handle")
    m.add_argument("--confirm-export-control", action="store_true", help="screenshots and photos were reviewed")
    m.set_defaults(func=_cmd_migrate)

    mo = sub.add_parser("month", help="the PDF of the entries logged in a month")
    mo.add_argument("--month", help="YYYY-MM (default: last month)"); mo.add_argument("--to", default="build")
    mo.set_defaults(func=_cmd_month)

    d = sub.add_parser("digest", help="the weekly summary (Markdown)")
    d.add_argument("--today"); d.add_argument("--days", type=int, default=7)
    d.set_defaults(func=_cmd_digest)

    ep = sub.add_parser("epics", help="EPICS settings: snapshot a PV group, restore a stored one")
    ep.add_argument("action", choices=["snapshot", "restore"])
    ep.add_argument("target", help="snapshot: the PV group; restore: the entry id")
    ep.add_argument("--out"); ep.add_argument("--label"); ep.add_argument("--group"); ep.add_argument("--yes", action="store_true")
    ep.set_defaults(func=_cmd_epics)

    ig = sub.add_parser("init-github", help="write the issue form and the workflows into .github/")
    ig.add_argument("--force", action="store_true", help="also replace existing workflow files")
    ig.set_defaults(func=_cmd_init_github)

    fi = sub.add_parser("from-issue", help="(the entry-from-issue workflow) a submitted form into an entry")
    fi.add_argument("number", type=int); fi.add_argument("--submitter", required=True); fi.add_argument("--repo", required=True)
    fi.set_defaults(func=_cmd_from_issue)

    cp = sub.add_parser("copy-permissions", help="projects with a permission to be copied into internal repositories")
    cp.set_defaults(func=_cmd_copy_permissions)

    s = sub.add_parser("schema", help="print the JSON Schema of the entry header")
    s.set_defaults(func=_cmd_schema)
    o = sub.add_parser("open-items", help="issues and todos nothing has resolved yet")
    o.add_argument("--project"); o.set_defaults(func=_cmd_open)

    a = ap.parse_args(argv)
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
