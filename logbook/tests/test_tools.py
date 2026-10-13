"""The tools around the format: new, cite, export, month, digest, pull, migrate, GitHub, EPICS."""

from __future__ import annotations

import io
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
import yaml

from lablogbook import check, cite, connect, github, migrate, newentry, projectcopy, reports
from lablogbook.book import open_book
from lablogbook.selection import Filter

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "logbook"
FIG = EXAMPLE / "entries/2026/figures/plot-example-transmission-scan-v2"
RUN = "2026-10-01-0930-aa-first-transmission-scan"
needs_render = pytest.mark.skipif(not (shutil.which("pandoc") and shutil.which("typst")), reason="pandoc and typst needed")


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True).stdout


def init_repo(d: Path, files_from: Path | None = None) -> Path:
    if files_from:
        shutil.copytree(files_from, d)
    else:
        d.mkdir(parents=True)
    git(d, "init", "-q", "-b", "main")
    git(d, "config", "user.email", "test@example.org")
    git(d, "config", "user.name", "Test")
    git(d, "add", "-A")
    git(d, "commit", "-q", "--allow-empty", "-m", "base")
    return d


@pytest.fixture
def book_dir(tmp_path):
    return init_repo(tmp_path / "book", EXAMPLE)


def draft(tmp: Path, header: dict, body: str = "Text.\n") -> Path:
    p = tmp / "draft.md"
    p.write_text("---\n" + yaml.safe_dump(header, sort_keys=False) + "---\n\n" + body)
    return p


# ------------------------------------------------------------------------------ new ----------
def test_new_standalone_from_a_draft(book_dir, tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    for ext in (".pdf", ".svg", ".png", ".yaml"):
        shutil.copy(FIG.with_suffix(ext), work / f"plot-new-thing-v1{ext}")
    d = draft(work, {"title": "A new scan", "project": "Example experiment", "kind": "run", "runs": ["r018"],
                     "figures": [{"file": "plot-new-thing-v1.pdf", "caption": "The new scan.", "alt": "A curve rising to a maximum and falling again."}]},
              "::: finding\nIt peaks.\n:::\n")
    header, body = newentry.read_draft(d)
    t = connect.target(book_dir)
    rc = newentry.create(t, header, body, work, newentry.Options(handle="aa", date="2026-10-06", time="14:05", today="2026-10-06"), out=io.StringIO())
    path = book_dir / "entries/2026/2026-10-06-1405-aa-a-new-scan.md"
    assert rc == 0 and path.exists()
    text = path.read_text()
    assert "date: 2026-10-06\n" in text and 'time: "14:05"' in text            # dates plain, time a string
    assert "file: figures/plot-new-thing-v1.pdf" in text
    for ext in (".pdf", ".svg", ".png", ".yaml"):                            # the figure's siblings came along
        assert (book_dir / f"entries/2026/figures/plot-new-thing-v1{ext}").exists()
    r = check.run(open_book(book_dir), check.Options(paths=[path], today="2026-10-06"))
    assert r.exit_code == 0, r.render()


def test_new_refuses_to_overwrite_a_file(book_dir, tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    (work / "transmission-scan-r017.csv").write_text("different\n")
    d = draft(work, {"title": "Clash", "project": "Example experiment",
                     "data": [{"file": "transmission-scan-r017.csv", "source": "x"}]})
    header, body = newentry.read_draft(d)
    with pytest.raises(newentry.NewError, match="already exists"):
        newentry.build(open_book(book_dir), header, body, work, newentry.Options(handle="aa", today="2026-10-06"))


def test_new_backfills_and_holds_pdf_attachments(book_dir, tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    (work / "wiring.pdf").write_bytes(b"%PDF-1.4\n")
    d = draft(work, {"title": "Wiring", "project": "Example experiment", "attachments": [{"file": "wiring.pdf"}]})
    header, body = newentry.read_draft(d)
    t = connect.target(book_dir)
    out = io.StringIO()
    rc = newentry.create(t, header, body, work, newentry.Options(handle="aa", date="2026-09-20", today="2026-10-06"), out=out)
    assert rc == 3 and "HELD" in out.getvalue()                               # waits for the confirmation
    text = next((book_dir / "entries/2026").glob("2026-09-20-*-aa-wiring.md")).read_text()
    assert "backfilled: 2026-10-06" in text                                   # written 16 days later


def test_new_in_a_connected_repository_pushes_a_branch(tmp_path, monkeypatch):
    remote = tmp_path / "central.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    seed = init_repo(tmp_path / "seed", EXAMPLE)
    git(seed, "remote", "add", "origin", str(remote))
    git(seed, "push", "-q", "origin", "main")
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", str(remote), str(clone)], check=True)
    project = init_repo(tmp_path / "project")
    (project / "logbook.yaml").write_text(f"central:\n  repository: example/central\n  clone: {clone}\n  project: Example experiment\n")
    monkeypatch.setattr(newentry.shutil, "which", lambda name: None)          # no gh: push only
    t = connect.target(project)
    assert t.connected
    out = io.StringIO()
    rc = newentry.create(t, {"title": "From the project"}, "Done.\n", project,
                         newentry.Options(handle="bb", time="10:00", today="2026-10-06", date="2026-10-06"), out=out)
    assert rc == 0, out.getvalue()
    branches = git(remote, "branch", "--list")
    assert "entry/bb/2026-10-06-1000-bb-from-the-project" in branches
    assert git(clone, "status", "--porcelain") == ""                         # the clone's checkout untouched
    assert git(clone, "worktree", "list").count("\n") == 1                   # the temporary worktree is gone


# ------------------------------------------------------------------------------ cite ---------
CROSSREF = {"message": {"type": "journal-article", "DOI": "10.1103/PhysRevLett.999.000001",
                        "title": ["A <i>new</i> measurement"], "container-title": ["Physical Review Letters"],
                        "short-container-title": ["Phys. Rev. Lett."], "volume": "999", "page": "000001",
                        "issued": {"date-parts": [[2025, 3]]},
                        "author": [{"family": "Author", "given": "Anna"}, {"family": "Builder", "given": "Ben"}]}}


def test_new_says_so_when_the_draft_is_missing(book_dir, tmp_path, capsys):
    from lablogbook import cli
    assert cli.main(["--root", str(book_dir), "new", "--from", str(tmp_path / "nope.md"), "--as", "aa", "--yes"]) == 1
    assert "no draft at" in capsys.readouterr().err


def test_cite_add_from_crossref(book_dir):
    book = open_book(book_dir)
    key, added = cite.add(book, "https://doi.org/10.1103/PhysRevLett.999.000001", fetch=lambda url: CROSSREF)
    assert added and key == "Author2025"
    text = book.bib_path.read_text()
    assert "shortjournal = {Phys. Rev. Lett.}" in text and "title        = {{A new measurement}}" in text
    again, added2 = cite.add(open_book(book_dir), "10.1103/PhysRevLett.999.000001", fetch=lambda url: 1 / 0)
    assert again == "Author2025" and not added2                               # not fetched or added twice
    r = check.run(open_book(book_dir), check.Options(paths=[book.bib_path]))
    assert r.exit_code == 0, r.render()


def test_cite_key_gets_a_letter_when_taken(book_dir):
    msg = json.loads(json.dumps(CROSSREF))
    msg["message"]["issued"] = {"date-parts": [[2019]]}
    msg["message"]["DOI"] = "10.5555/other"
    key, _ = cite.add(open_book(book_dir), "10.5555/other", fetch=lambda url: msg)
    assert key == "Author2019a"


# ------------------------------------------------------------------------------ export, month, digest --
def test_filter_selects_like_the_view():
    book = open_book(EXAMPLE)
    assert [e.id for e in Filter(kinds=["meeting"]).apply(book)] == ["2026-10-05-1100-cc-weekly-meeting"]
    assert len(Filter(people=["bb"]).apply(book)) == 1
    assert len(Filter(query="cage supply").apply(book)) >= 1
    assert Filter(date_from="2026-10-03").apply(book)[0].date == "2026-10-03"


@needs_render
def test_export_pdf_with_roles(tmp_path):
    out = tmp_path / "x.pdf"
    path, n = reports.export(open_book(EXAMPLE), Filter(projects=["Example experiment"], kinds=["run"]), out,
                             "a-author-example", "c-chair-example", "a visitor", anonymise=True)
    assert path == out.resolve() and n == 1 and out.stat().st_size > 10_000


def test_digest_lists_open_items_and_new_entries():
    text = reports.digest(open_book(EXAMPLE), today="2026-10-06", days=7)
    assert "new entries" in text and "### Open items (2)" in text and "todo-repeat" in text


@needs_render
def test_month_pdf(book_dir, tmp_path):
    path, n = reports.month_pdf(open_book(book_dir), "2026-10", tmp_path)   # committed today; counts by commit month
    month = reports.logged_month(open_book(book_dir), "2026-10")
    assert n == len(month) or n == 0


# ------------------------------------------------------------------------------ pull ---------
def _connected_project(tmp_path, monkeypatch, visibility: str):
    clone = init_repo(tmp_path / "clone", EXAMPLE)
    project = init_repo(tmp_path / "project")
    (project / "logbook.yaml").write_text(f"central:\n  repository: example/central\n  clone: {clone}\n  project: Example experiment\n")
    monkeypatch.setenv("LOGBOOK_VISIBILITY", visibility)
    return project, clone


def test_pull_writes_a_self_contained_copy(tmp_path, monkeypatch):
    project, _ = _connected_project(tmp_path, monkeypatch, "PRIVATE")
    central = connect.local_config(project)[1]["central"]
    dest = projectcopy.pull(project, central, update=False, today="2026-10-06")
    assert (dest / "GENERATED.md").exists() and (dest / "SUMMARY.md").exists()
    assert len(list((dest / "entries/2026").glob("*.md"))) == 5
    assert (dest / "entries/2026/figures/plot-example-transmission-scan-v1.svg").exists()
    assert (dest / "wiki/projects/example-experiment.md").exists()
    summary = (dest / "SUMMARY.md").read_text()
    assert "Open items (2)" in summary and "About Example experiment" in summary
    r = check.run(open_book(dest), check.Options(today="2026-10-06"))       # the copy is a valid log book
    assert r.exit_code == 0, r.render()
    projectcopy.pull(project, central, update=False, today="2026-10-06")     # and it can be pulled again


@pytest.mark.parametrize("vis,ok", [("PUBLIC", False), ("INTERNAL", False), ("PRIVATE", True)])
def test_pull_visibility_guard(tmp_path, monkeypatch, vis, ok):
    project, _ = _connected_project(tmp_path, monkeypatch, vis)
    central = connect.local_config(project)[1]["central"]
    if ok:
        projectcopy.pull(project, central, update=False)
    else:
        with pytest.raises(projectcopy.CopyError):
            projectcopy.pull(project, central, update=False)


def test_pull_into_internal_with_a_current_permission(tmp_path, monkeypatch):
    project, clone = _connected_project(tmp_path, monkeypatch, "INTERNAL")
    p = clone / "projects.yaml"
    p.write_text(p.read_text().replace("  wiki: projects/example-experiment", "  wiki: projects/example-experiment\n  copy_internal_until: 2099-01-01"))
    projectcopy.pull(project, connect.local_config(project)[1]["central"], update=False)


def test_pull_never_touches_a_folder_it_did_not_make(tmp_path, monkeypatch):
    project, _ = _connected_project(tmp_path, monkeypatch, "PRIVATE")
    (project / "logbook").mkdir()
    (project / "logbook" / "notes.txt").write_text("mine\n")
    with pytest.raises(projectcopy.CopyError, match="not made by"):
        projectcopy.pull(project, connect.local_config(project)[1]["central"], update=False)


# ------------------------------------------------------------------------------ migrate ------
TYPST = r'''#import "labnotes-template.typ": *
#show: labnotes.with(title: "Test Log Book", project: "Test project", author: "A. Author")

= Project background

#context-box[*Programme.* What the project is for.]
#refs(("Code": raw("src/"),))

#entry("2026-09-04", "Old style entry with a figure", tags: ("a", "b"),
  authors: [A. Author (with assistance from Claude Code)])[
Text with HV_Drift and M2_2–M2_6 by 5 V.

#finding[It *works*: 38 %.]
#figure(image("fig-test.svg", width: 100%), caption: [The test figure.])
#refs(("Script": raw("scripts/x.py"), "Note": [see `y`]))
]

#day("2026-10-01", "A day", authors: [A. Author])[

#note("Ion source", "First note of the day", tags: ("scan",))[
#decision[Use −120 V.]
#todo[
  - Repeat at 1 kV.
]
]

#note("Beamline", "Second note")[
A table:
#figure(table(columns: 2, [*a*], [*b*], [1], [2]), caption: [Small.])
]

#day("2026-10-02", "Nested day (a missing bracket before it)", authors: [A. Author, B. Builder])[
#note("Ion source", "Note in the nested day")[Plain text.]
]
]
'''


def test_migrate_a_typst_log_book(tmp_path):
    src = init_repo(tmp_path / "src")
    (src / "notes").mkdir()
    shutil.copy(FIG.with_suffix(".svg"), src / "notes" / "fig-test.svg")
    (src / "notes" / "test-logbook.typ").write_text(TYPST)
    git(src, "add", "-A")
    git(src, "commit", "-q", "-m", "the log book")
    book = open_book(init_repo(tmp_path / "book", EXAMPLE))
    r = migrate.migrate(src / "notes" / "test-logbook.typ", book, project="Example experiment")
    assert len(r.entries) == 4 and not r.unknown_authors, r.render(book)
    texts = {p.stem: p.read_text() for p in r.entries}
    old = next(t for k, t in texts.items() if "old-style" in k)
    assert "HV_Drift and M2_2–M2_6" in old                                    # in-word underscores survive
    assert "::: finding" in old and "**works**" in old
    assert "with: claude" in old and "migrated_from: src@" in old and "logged:" in old
    assert "backfilled:" in old                                               # committed today, dated 2026-09-04
    assert "Script: scripts/x.py" in old and "file: figures/fig-test-v1.svg" in old
    first = next(t for k, t in texts.items() if "first-note" in k)
    assert "subproject: Ion source" in first and "::: decision" in first and "::: todo" in first
    second = next(t for k, t in texts.items() if "second-note" in k)
    assert "| **a** | **b** |" in second                                      # a figure without an image: the table kept
    nested = next(t for k, t in texts.items() if "nested-day" in k)
    assert "authors: [aa, bb]" in nested
    assert r.background.name == "example-experiment-migrated.md"            # the existing page is not overwritten
    wiki = r.background.read_text()
    assert "Programme." in wiki and "**Code:** `src/`" in wiki
    rep = check.run(open_book(book.root), check.Options(today="2026-10-13"))
    assert not [f for f in rep.findings if f.level == "fail"], rep.render()


# ------------------------------------------------------------------------------ GitHub -------
ISSUE = """### Title

Drift traced to the cage supply

### Kind

note

### Project

Example experiment

### Subproject

Beamline

### Co-authors

A. Author (aa)

### Apparatus

Example ion source (source)

### Tags

drift, high voltage

### Date of the work

_No response_

### Corrects

_No response_

### Resolves

2026-10-01-0930-aa-first-transmission-scan#todo-repeat

### Entry

::: finding
The supply follows the lab temperature.
:::

### Figures, data and attachments

![plot-x-v1.svg](https://github.com/user-attachments/assets/abc)

Caption: The drift.
Alt: Supply voltage against time, rising with the lab temperature.

[plot-x-v1.pdf](https://github.com/user-attachments/files/1/plot-x-v1.pdf)

[readings.csv](https://github.com/user-attachments/files/2/readings.csv)
Source: the supply's log, Drive folder Example/Data/Cage

### Export control

- [x] No file I attached holds export-controlled technical data
"""


def test_issue_form_and_parsing(tmp_path):
    book = open_book(EXAMPLE)
    form = github.issue_form(book)
    labels = {b["attributes"]["label"] for b in form["body"] if "label" in b.get("attributes", {})}
    assert set(github.FORM_LABELS) <= labels                                  # every field the parser reads exists
    people = next(b for b in form["body"] if b.get("id") == "coauthors")["attributes"]["options"]
    assert "A. Author (aa)" in people
    answers = github.parse_issue_body(ISSUE)
    assert answers["title"] == "Drift traced to the cage supply" and answers["date"] == ""
    files = github.parse_files(answers["files"])
    assert [f["name"] for f in files] == ["plot-x-v1.svg", "plot-x-v1.pdf", "readings.csv"]

    def fake(url, dest, token):
        src = {"plot-x-v1.svg": FIG.with_suffix(".svg"), "plot-x-v1.pdf": FIG.with_suffix(".pdf")}.get(dest.name)
        dest.write_bytes(src.read_bytes() if src else b"t,v\n0,1\n")
        return dest
    header, body = github.draft_from_issue(book, answers, files, tmp_path, None, fetch=fake)
    assert header["authors"] == ["aa"] and header["apparatus"] == ["source"] and header["tags"] == ["drift", "high voltage"]
    assert header["figures"][0]["caption"] == "The drift." and header["figures"][0]["file"].endswith(".pdf")
    assert header["data"][0]["source"].startswith("the supply's log")
    assert header["resolves"] == ["2026-10-01-0930-aa-first-transmission-scan#todo-repeat"]


def test_init_github_writes_parseable_files(book_dir):
    written = github.init_github(open_book(book_dir))
    assert ".github/ISSUE_TEMPLATE/new-entry.yml" in written
    assert len([w for w in written if w.startswith(".github/workflows/")]) == 6
    for w in written:
        data = yaml.safe_load((book_dir / w).read_text())
        assert data, w
    wf = yaml.safe_load((book_dir / ".github/workflows/logbook-checks.yml").read_text())
    assert "entry-checks" in wf["jobs"]
    for w in written:      # no ${{ … }} pasted into a shell script (injection)
        if w.startswith(".github/workflows/"):
            for job in yaml.safe_load((book_dir / w).read_text())["jobs"].values():
                for step in job.get("steps", []):
                    assert "${{" not in step.get("run", ""), (w, step.get("name"))


# ------------------------------------------------------------------------------ EPICS --------
def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture
def ioc(monkeypatch):
    pytest.importorskip("caproto")
    port = _free_port()
    env = {"EPICS_CA_SERVER_PORT": str(port), "EPICS_CA_ADDR_LIST": "127.0.0.1", "EPICS_CA_AUTO_ADDR_LIST": "NO",
           "EPICS_CAS_INTF_ADDR_LIST": "127.0.0.1", "EPICS_CA_REPEATER_PORT": str(_free_port())}
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    proc = subprocess.Popen([sys.executable, str(Path(__file__).parent / "soft_ioc.py")], env={**os.environ, **env},
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    from caproto.sync import client
    for _ in range(50):
        try:
            client.read("SRC:Extract", timeout=0.5)
            break
        except Exception:   # noqa: BLE001 - not up yet
            time.sleep(0.2)
    yield client
    proc.terminate()
    proc.wait(5)


def test_epics_snapshot_and_restore(ioc, book_dir, tmp_path):
    from lablogbook import epicsio
    book = open_book(book_dir)
    snap = epicsio.snapshot(book, "source-tune", tmp_path / "snap.json", "test")
    data = json.loads(snap.read_text())
    vals = {p["name"]: p for p in data["pvs"]}
    assert vals["SRC:Extract"]["value"] == -110.0 and vals["SRC:Extract"]["unit"] == "V"
    assert vals["SRC:HV_Offset"]["severity"] == "NO_ALARM"
    assert epicsio.check_snapshot if hasattr(epicsio, "check_snapshot") else True
    from lablogbook.epics import check_snapshot
    assert check_snapshot(snap, "source-tune", ["SRC:HV_Offset", "SRC:Extract", "SRC:Laser_Energy"]) == []
    # the example entry stored -120 V: restore asks, then writes
    stored = epicsio.stored(book, RUN, "source-tune")[0][0]
    out = io.StringIO()
    assert epicsio.restore(stored, lambda q: False, out) == 0 and "nothing written" in out.getvalue()
    assert epicsio.restore(stored, lambda q: True, out) == 1
    assert ioc.read("SRC:Extract", timeout=2).data[0] == -120.0
    assert epicsio.restore(stored, lambda q: True, io.StringIO()) == 0     # now nothing differs
