# Log-book entries as Markdown files: the format

A log book in which **every entry is one Markdown file** with a YAML header, kept in git and
checked before it is submitted. It records what happened, when and why: decisions, findings
with their numbers, problems and their fixes, open items. The repository and its documents say
how things *are*; the log book says what *happened*.

This is the format and the checker (`logbook/`, since v2026.10.16). The PDF build with the lab
notebook template and the searchable HTML view follow in the next releases. The Typst log books
(`#day`, `#note`, `#entry`, `docs/LOGBOOK_GUIDE.md`) keep working unchanged; moving one to this
format is offered by a migration tool, never forced. A complete example: `examples/logbook/`.

## Standalone or central

- **Standalone** (the default): any repository, entries in `entries/YYYY/`, any author names,
  any project names. Nothing else is needed.
- **Central** (several people, one repository): `logbook.yaml` at the root and three registries,
  `people.yaml`, `projects.yaml`, `apparatus.yaml` (examples in `examples/logbook/`). Then
  authors are handles from `people.yaml`, projects, sub-projects and apparatus must exist, and a
  pull request may only add entries whose first author is the person submitting. Nothing in the
  format or the checker needs a particular organisation, Drive or account.

## One entry

`entries/2026/2026-10-01-0930-aa-first-transmission-scan.md`: the file name is the entry's
**id**, `YYYY-MM-DD-HHMM-<handle>-<slug>`, in the folder of its year. Date and time are those of
the work (local time); the handle is the first author's; the slug is a few words of the title.

```markdown
---
date: 2026-10-01
time: "09:30"
authors: [aa]                 # first = the person submitting; more if others took part
with: claude                  # optional: written with assistance from Claude Code
kind: run                     # see "Kinds"
project: Example experiment
subproject: Ion source        # optional
apparatus: [source, beamline] # optional
title: First transmission scan of the extraction voltage
tags: [transmission]
runs: ["DAQ run r017"]
parameters:
  - {name: SRC:HV_Offset, value: 3000, unit: V}
figures:
  - file: figures/plot-example-transmission-scan-v1.pdf
    caption: "Transmission against extraction voltage (run r017)."
    alt: "Line plot of transmission ... maximum of 38 percent at -120 V ..."
data:
  - file: data/transmission-scan-r017.csv
    describes: plot-example-transmission-scan-v1
    source: "DAQ run r017; raw traces in the Drive folder Example/Data/Transmission/r017"
epics:
  - {file: epics/source-tune-2026-10-01T0930.json, group: source-tune}
---

Context in plain text, with [@Author2019] cited and [[2026-09-30-1600-bb-cage-rewired]] linked.

::: finding
Transmission peaks at −120 V with 38 %.
:::

::: issue {#issue-drift}
*Symptom.* The peak moves by 5 V in 20 minutes. Cause unknown. Open.
:::
```

Only `date`, `authors`, `kind`, `project` and `title` are required: a quick note stays quick.
The full list of header fields, with their meaning, is the JSON Schema
(`logbook/src/lablogbook/data/entry.schema.json`, or `logbook schema`).

**Never changed after it is merged.** A wrong number or conclusion is corrected by a new entry
(`kind: correction`, `corrects: <id>`) that says what was wrong; the views show the correction
with the old entry. Removing something that must not be stored is a `redaction` by an admin,
which names the kind of content and the reason, never the content.

**Dates.** `date` is when the work was done. An entry written more than two days later
(`late_days`) carries `backfilled: <the day it was written>`. The time an entry was *logged* is
the time its pull request was merged (GitHub's clock), shown next to `date` by the views.

## Kinds

| kind | for | the checker wants |
|---|---|---|
| `note` | any piece of work | |
| `run` | a measurement or beam time | `runs`, `parameters` (recommended) |
| `calibration` | a calibration | `apparatus`, `valid_until` (recommended) |
| `maintenance` | work on the apparatus | `apparatus`, `valid_until` (recommended) |
| `incident` | vacuum loss, HV trip, interlock, damage: never health information | `apparatus` |
| `meeting` | who was there, what was decided | `attendees` (recommended) |
| `correction` | what was wrong in an earlier entry | `corrects` |
| `redaction` | that something was removed, never what | `redacts`, `level` |

A central book adds kinds in its own `kinds.yaml` (same form as
`logbook/src/lablogbook/data/kinds.yaml`).

## Blocks

The body is Markdown. Five blocks carry the lab notebook's callouts, as fenced divs:
`::: decision`, `::: finding`, `::: issue`, `::: todo`, `::: context`, plus `::: incident`.
An `issue` or `todo` with an id (`::: todo {#todo-repeat}`) stays **open** until a later entry
lists it under `resolves: [<entry-id>#todo-repeat]`; the views show both directions, and
`logbook open-items` lists everything still open. Math is `$…$` (LaTeX).

## Links

Every link is written once, in the newer entry, and the views compute the other direction.

| link | written as |
|---|---|
| to an entry, or one of its blocks | `[[<entry-id>]]`, `[[<entry-id>#issue-drift]]` in the text |
| related entries (a thread, a newer version of a figure) | `related: [<entry-id>, …]` |
| a correction | `corrects: <entry-id>` |
| an open item settled | `resolves: [<entry-id>#<block-id>]` |
| a wiki page | `[[wiki:apparatus/source]]` |
| a reference | `[@Author2019]`, `[see @Author2019; @Solo2021]` |

## The wiki and the references

`wiki/` holds what is true *now*: project pages, apparatus pages, procedures, how-tos. It is
living text (changed through pull requests like any file, with its history in git), checked for
compliance like entries but not append-only.

`wiki/references.bib` is the reference list: BibTeX, every record with a DOI or an ISBN, keys
`LastnameYYYY`, the journal's short title in `shortjournal`, titles' capitals kept with double
braces. A citation whose key is missing fails the check. Citations render as
`Author A.++ Phys. Rev. Lett. 123, 456 (2019)` ("++": and others), linked to the DOI;
`logbook/src/lablogbook/data/karthein-lab.csl` is the style.

## Figures, data, attachments, settings

Paths are relative to the entry's folder (`entries/YYYY/`).

- **Figures** are saved with `labfig` (`matplotlib/labfig.py`) as versions:
  `figures/<name>-vN.pdf`, `.svg`, `.png` and the record `<name>-vN.yaml`. A plot needs its PDF
  (print) and its SVG (HTML view); photos and screenshots may be raster. A changed figure is a
  new version in a new entry (`related:` to the one that showed the old version); an old entry
  keeps showing what it showed. `library:` names the folder in a figure library.
- **Data**: the processed numbers a figure shows (CSV, JSON), with `source:` saying where the
  raw data lives. Raw data never goes into the log book.
- **Attachments**: any other file. A **PDF attachment, or a figure that is not a plot**, is
  *held* until the author confirms, per file, that it holds no export-controlled technical data
  (`export_control_confirmed: true`). If in doubt: do not confirm; name the folder that holds the
  file instead.
- **EPICS settings**: `epics/<group>-<time>.json`, a snapshot of a named group of process
  variables (format `lab-epics-snapshot/1`, see `logbook/src/lablogbook/epics.py`); the groups
  are defined per apparatus in `apparatus.yaml`.
- Sizes: over 2 MB warns, over 5 MB fails (`limits` in `logbook.yaml`).

## The checker

```sh
uv run --project lab/logbook logbook check                         # everything
uv run --project lab/logbook logbook check entries/2026/<id>.md    # one entry
uv run --project lab/logbook logbook check --base origin/main --submitter <login> --ci   # a pull request
```

| it checks | if not |
|---|---|
| header against the schema; file name, folder, date, time, handle | fail |
| kind known; its required fields | fail (recommended fields: warning) |
| authors, projects, sub-projects, apparatus in the registries (central book) | fail |
| dated in the future; late without `backfilled` | fail |
| links, `corrects`, `related`, `redacts` point to existing entries; `resolves` to an open issue or todo | fail |
| citations exist in the reference list; new references have a DOI or ISBN | fail |
| files exist, inside `entries/`; sizes; plots have their SVG; drafts are not used; versions in figure names | fail / warning |
| EPICS snapshots parse; PVs belong to the group | fail |
| secrets (keys, tokens, private keys), home-folder paths, Drive links with ids | fail |
| FERPA patterns: nine-digit numbers, SSN-shaped numbers, grades, transcripts of records, enrolment, someone named as a student who is not a member, a university address of a non-member | fail; `reviewed: ferpa` in the header after reading turns them into recorded warnings |
| health words | fail; `reviewed: health` likewise |
| proprietary or export-control wording | warning |
| PDF attachments and non-plot figures | **held** until `export_control_confirmed: true` |
| in a pull request: existing entries and their files never change (except under a redaction by an admin); files outside `entries/` and `wiki/` only by an admin; the first author of a new entry is the submitter (an admin may submit on behalf) | fail |
| people who logged on the same project in the last 14 days | note: proposed as co-authors |

It finds patterns, not meaning: passing it does not make an entry compliant, reading it again
does. With `--ci` it never prints the text a finding matched, only file, line and kind of hit.
Exit code 0 fine, 1 failed, 3 held.
