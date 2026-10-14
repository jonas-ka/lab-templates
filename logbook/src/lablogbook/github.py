"""A central log book on GitHub: the "New entry" issue form, entries made from submitted forms,
and the workflow files (`logbook init-github` writes them into `.github/`).

The form is generated from the registries (projects, people, apparatus, kinds), so its menus
match the book; run `logbook init-github` again after a registry changes.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import urllib.request
from importlib import resources
from pathlib import Path

import yaml

from .book import Book

NO_RESPONSE = "_No response_"
FORM_LABELS = {  # issue-form label -> field
    "Title": "title", "Kind": "kind", "Project": "project", "Subproject": "subproject", "Co-authors": "coauthors",
    "Apparatus": "apparatus", "Tags": "tags", "Date of the work": "date", "Corrects": "corrects",
    "Resolves": "resolves", "Entry": "body", "Figures, data and attachments": "files",
    "Export control": "export_control",
}


class IssueError(RuntimeError):
    pass


def issue_form(book: Book) -> dict:
    people = [f"{p.name} ({h})" for h, p in sorted((book.people or {}).items(), key=lambda x: x[1].name)]
    projects = list(book.projects or {}) or ["(add projects to projects.yaml)"]
    apparatus = [f"{v.get('name', k)} ({k})" for k, v in (book.apparatus or {}).items()]
    body = [
        {"type": "markdown", "attributes": {"value": (
            "Write one piece of work: what you did, what you found (with the numbers), what you decided and why, "
            "what is still open. It becomes a pull request that merges itself when the checks pass; you are the first author. "
            "Never: grades or other student records, health information, passwords, export-controlled documents "
            "(link them where they live instead).")}},
        {"type": "input", "id": "title", "attributes": {"label": "Title"}, "validations": {"required": True}},
        {"type": "dropdown", "id": "kind", "attributes": {"label": "Kind", "options": list(book.kinds), "default": 0}},
        {"type": "dropdown", "id": "project", "attributes": {"label": "Project", "options": projects}, "validations": {"required": True}},
        {"type": "input", "id": "subproject", "attributes": {"label": "Subproject", "description": "Optional."}},
    ]
    if people:
        body.append({"type": "dropdown", "id": "coauthors", "attributes": {
            "label": "Co-authors", "description": "Others who took part (you are the first author).", "multiple": True, "options": people}})
    if apparatus:
        body.append({"type": "dropdown", "id": "apparatus", "attributes": {"label": "Apparatus", "multiple": True, "options": apparatus}})
    body += [
        {"type": "input", "id": "tags", "attributes": {"label": "Tags", "description": "Comma separated."}},
        {"type": "input", "id": "date", "attributes": {"label": "Date of the work", "description": "YYYY-MM-DD; empty for today."}},
        {"type": "input", "id": "corrects", "attributes": {"label": "Corrects", "description": "The id of an entry this one corrects (a correction)."}},
        {"type": "input", "id": "resolves", "attributes": {"label": "Resolves", "description": "Open items this entry settles: <entry-id>#<block-id>, comma separated."}},
        {"type": "textarea", "id": "body", "attributes": {"label": "Entry", "description": (
            "Markdown. Callouts: a line `::: finding`, the text, a line `:::` (also decision, issue, todo, context, incident; "
            "`::: todo {#todo-1}` gives an open item an id). Link entries as [[entry-id]], cite as [@Key].")},
         "validations": {"required": True}},
        {"type": "textarea", "id": "files", "attributes": {"label": "Figures, data and attachments", "description": (
            "Drag files here, one paragraph each. Under a figure write `Caption: …` and `Alt: …` (what the figure shows, "
            "for readers who cannot see it); a plot needs its PDF and its SVG (drag both). Under a data file write "
            "`Source: …` (where the raw data lives).")}},
        {"type": "checkboxes", "id": "export_control", "attributes": {"label": "Export control", "options": [
            {"label": "No file I attached holds export-controlled technical data (manuals, vendor documents, controlled drawings)."}]}},
    ]
    return {"name": "New log-book entry", "description": "Write an entry for the log book.", "title": "Entry: ",
            "labels": ["new-entry"], "body": body}


def parse_issue_body(text: str) -> dict:
    """The answers of a submitted issue form: {field: text}."""
    out, cur, buf = {}, None, []
    for line in (text or "").splitlines():
        m = re.match(r"^###\s+(.+?)\s*$", line)
        if m and m.group(1) in FORM_LABELS:
            if cur:
                out[cur] = "\n".join(buf).strip()
            cur, buf = FORM_LABELS[m.group(1)], []
        elif cur:
            buf.append(line)
    if cur:
        out[cur] = "\n".join(buf).strip()
    return {k: ("" if v == NO_RESPONSE else v) for k, v in out.items()}


_LINK = re.compile(r"!?\[([^\]]*)\]\((https://[^)\s]+)\)|(https://github\.com/user-attachments/\S+)")


def parse_files(text: str) -> list[dict]:
    """Paragraphs of the files field: [{url, name, caption, alt, source}]."""
    items = []
    for para in re.split(r"\n\s*\n", text or ""):
        def field(k):
            mm = re.search(rf"^\s*{k}\s*:\s*(.+)$", para, re.M | re.I)
            return mm.group(1).strip() if mm else None
        m = _LINK.search(para)
        if not m:   # "Caption: …" in a paragraph of its own belongs to the file above it
            if items:
                for k in ("caption", "alt", "source"):
                    items[-1][k] = items[-1][k] or field(k)
            continue
        url = m.group(2) or m.group(3)
        name = (m.group(1) or "").strip() or url.rsplit("/", 1)[-1]
        items.append({"url": url, "name": name, "caption": field("caption"), "alt": field("alt"), "source": field("source")})
    return items


def download(url: str, dest: Path, token: str | None) -> Path:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"} if token else {})
    with urllib.request.urlopen(req, timeout=60) as r:
        dest.write_bytes(r.read())
    return dest


def draft_from_issue(book: Book, answers: dict, files: list[dict], workdir: Path, token: str | None,
                     fetch=download) -> tuple[dict, str]:
    """(header, body) of a draft for `logbook new`, files downloaded into `workdir`."""
    h: dict = {"title": answers.get("title", "").strip(), "kind": answers.get("kind") or "note",
               "project": answers.get("project", "").strip()}
    for k in ("subproject", "date", "corrects"):
        if answers.get(k):
            h[k] = answers[k].strip()
    if answers.get("tags"):
        h["tags"] = [t.strip() for t in answers["tags"].split(",") if t.strip()]
    if answers.get("resolves"):
        h["resolves"] = [t.strip() for t in answers["resolves"].split(",") if t.strip()]
    if answers.get("coauthors"):
        h["authors"] = re.findall(r"\((\w+)\)", answers["coauthors"])
    if answers.get("apparatus"):
        h["apparatus"] = re.findall(r"\(([\w-]+)\)", answers["apparatus"])
    confirmed = "[x]" in answers.get("export_control", "").lower()
    by_stem: dict[str, list[dict]] = {}
    for f in files:
        local = fetch(f["url"], workdir / re.sub(r"[^\w.-]", "_", f["name"]), token)
        f["local"] = local
        by_stem.setdefault(local.stem, []).append(f)
    for stem, group in by_stem.items():
        exts = {g["local"].suffix.lower(): g for g in group}
        meta = next((g for g in group if g.get("caption") or g.get("alt")), group[0])
        if exts.keys() & {".pdf", ".svg", ".png", ".jpg", ".jpeg"} and not (len(exts) == 1 and ".pdf" in exts and not meta.get("caption")):
            main = exts.get(".pdf") or exts.get(".svg") or exts.get(".png") or exts.get(".jpg") or exts.get(".jpeg")
            kind = "plot" if (".svg" in exts or ".pdf" in exts) else "photo"
            item = {"file": str(main["local"]), "caption": meta.get("caption") or stem, "alt": meta.get("alt") or ""}
            if kind != "plot":
                item["kind"] = kind
                if confirmed:
                    item["export_control_confirmed"] = True
            h.setdefault("figures", []).append(item)
        else:
            for ext, g in exts.items():
                if ext in (".csv", ".json", ".txt", ".npz", ".tsv"):
                    h.setdefault("data", []).append({"file": str(g["local"]), "source": g.get("source") or "see the entry"})
                else:
                    a = {"file": str(g["local"])}
                    if confirmed:
                        a["export_control_confirmed"] = True
                    h.setdefault("attachments", []).append(a)
    return h, answers.get("body", "")


# ------------------------------------------------------------------------------ init-github --
def templates() -> dict[str, str]:
    root = resources.files("lablogbook").joinpath("data/github")
    out = {}
    for sub in ("workflows",):
        for f in root.joinpath(sub).iterdir():
            if f.name.endswith(".yml"):
                out[f".github/{sub}/{f.name}"] = f.read_text(encoding="utf-8")
    return out


def init_github(book: Book, force: bool = False) -> list[str]:
    """Write the issue form and the workflows into the book's repository; returns what was written."""
    written = []
    files = templates()
    form = yaml.safe_dump(issue_form(book), sort_keys=False, allow_unicode=True, width=10_000)
    files[".github/ISSUE_TEMPLATE/new-entry.yml"] = "# Generated by `logbook init-github` from the registries; run it again after they change.\n" + form
    files[".github/ISSUE_TEMPLATE/config.yml"] = "blank_issues_enabled: true\n"
    for rel, text in files.items():
        p = book.root / rel
        if p.exists() and not force and not rel.endswith("new-entry.yml"):
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        written.append(rel)
    return written


# ------------------------------------------------------------------------------ from-issue ----
def _gh(*args: str, check: bool = True) -> str:
    from . import connect
    return connect.run(["gh", *args], check=check)


def from_issue(book: Book, number: int, submitter: str, repo: str, out) -> int:
    """Run inside a checkout of the central log book (the entry-from-issue workflow)."""
    from . import check, connect, newentry
    from .book import open_book

    issue = json.loads(_gh("issue", "view", str(number), "--repo", repo, "--json", "body,title,state"))
    branch = f"entry/issue-{number}"
    # One issue, one entry: an issue that is closed, or whose entry has merged, is done. (Opening an
    # issue with its label fires two events; an edit after the merge must not make a second entry.)
    merged = _gh("pr", "list", "--repo", repo, "--head", branch, "--state", "merged", "--json", "number",
                 "-q", "length", check=False).strip()
    if issue.get("state", "OPEN") != "OPEN" or merged not in ("", "0"):
        print(f"issue #{number} is already done", file=out)
        return 0
    answers = parse_issue_body(issue.get("body", ""))
    person = book.person_by_login(submitter)

    def tell(text: str) -> None:
        _gh("issue", "comment", str(number), "--repo", repo, "--body", text, check=False)

    if book.people is not None and person is None:
        tell(f"@{submitter} is not in people.yaml, so this cannot become an entry yet. Ask the PI to add you.")
        return 1
    root = book.root
    connect.run(["git", "-C", str(root), "fetch", "-q", "origin", "main"])
    connect.run(["git", "-C", str(root), "switch", "-q", "-C", branch, "origin/main"])
    with tempfile.TemporaryDirectory() as tmp:
        try:
            header, body = draft_from_issue(book, answers, parse_files(answers.get("files", "")), Path(tmp),
                                            os.environ.get("GH_TOKEN"))
            opts = newentry.Options(handle=person.handle if person else submitter)
            path, h, body = newentry.build(open_book(root), header, body, Path(tmp), opts)
        except Exception as e:   # noqa: BLE001 - the author sees what went wrong on the issue
            tell(f"This form could not be turned into an entry: {e}\n\nEdit the issue to try again.")
            return 1
    name = person.name if person else submitter
    email = (person.email if person and person.email else f"{submitter}@users.noreply.github.com")
    connect.run(["git", "-C", str(root), "add", "-A", str(book.entries_dir)])
    connect.run(["git", "-C", str(root), "-c", f"user.name={name}", "-c", f"user.email={email}", "commit", "-q",
                 "-m", f"Entry: {h['title']}\n\nFrom issue #{number} by @{submitter}."])
    report = check.run(open_book(root), check.Options(base="origin/main", submitter=submitter, ci=True))
    if report.exit_code:
        tell("The entry did not pass the checks. Edit the issue to fix it; the form is read again.\n\n```\n"
             + report.render(ci=True) + "\n```")
        print(report.render(ci=True), file=out)
        return report.exit_code
    connect.run(["git", "-C", str(root), "push", "-q", "-f", "origin", branch])
    sha = connect.run(["git", "-C", str(root), "rev-parse", "HEAD"]).strip()
    url = _gh("pr", "create", "--repo", repo, "--head", branch, "--base", "main", "--title", f"Entry: {h['title']}",
              "--body", f"From #{number}, written by @{submitter}.\n\nCo-authored-by: {name} <{email}>",
              check=False).strip()
    if not url:
        url = _gh("pr", "view", branch, "--repo", repo, "--json", "url", "-q", ".url", check=False).strip()
    _gh("api", f"repos/{repo}/statuses/{sha}", "-f", "state=success", "-f", "context=entry-checks",
        "-f", f"description=checked in entry-from-issue as @{submitter}", check=False)
    _gh("pr", "merge", "--repo", repo, "--auto", "--squash", url, check=False)
    # A merge by the workflow's token does not apply "Closes #N", so the issue is closed here.
    _gh("issue", "close", str(number), "--repo", repo, "--comment",
        f"Entry `{path.stem}` passed the checks: {url} (it merges itself).", check=False)
    print(f"pull request: {url}", file=out)
    return 0
