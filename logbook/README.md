# logbook: log-book entries as Markdown files

A log book in which every entry is one Markdown file with a YAML header, kept in git, checked
before it is submitted, and (from the next releases on) rendered as a PDF with the lab notebook
template and as a searchable HTML view. The format is described in
[`../docs/LOGBOOK_FORMAT.md`](../docs/LOGBOOK_FORMAT.md); a worked example is in
[`../examples/logbook/`](../examples/logbook/).

**Standalone by default.** In any repository, put entries in `entries/YYYY/` and run the
checker; nothing else is needed. A *central* log book (several people, one repository) adds
`logbook.yaml` and registries of people, projects and apparatus; then authorship, projects and
apparatus are checked too.

```sh
# from a repository that carries lab-templates in lab/
uv run --project lab/logbook logbook check                       # every entry, the wiki, the references
uv run --project lab/logbook logbook check entries/2026/<id>.md  # one entry
uv run --project lab/logbook logbook check --base origin/main --submitter <github-login> --ci   # a pull request
uv run --project lab/logbook logbook open-items                  # issues and todos nothing has resolved
uv run --project lab/logbook logbook schema                      # the header's JSON Schema
```

Exit code 0: fine (warnings and notes allowed); 1: something fails; 3: held (an attachment
waits for the author's export-control confirmation).

Tests: `uv run --project logbook --extra test pytest logbook/tests` (from lab-templates).
The existing Typst log books (`#day`, `#note`, `#entry`) keep compiling unchanged; this is an
alternative, not a replacement forced on anyone.
