# Changelog

Consumers read this before `scripts/lab-templates.sh pull <tag>`.

## v2026.10.12 (2026-10-13)

From redrawing the lab's Drive figures with `labfig`:
- `labfig.save` works on a figure the script already closed (`plt.close(fig)` drops the canvas
  in matplotlib 3.11; `save` gives it an Agg canvas again; the drawing is unchanged).
- The record keeps the **command line** the script was run with (`command:`; absolute paths
  made relative to the figure folder or shortened to the file name) and an optional `note=`
  for anything else needed to redraw exactly (e.g. an environment setting).
- `code=` takes a list: the script and the modules it imports are all copied per version
  (`code/<stem>-vN.py`); the record lists the copies (`code.copies`).

## v2026.10.11 (2026-10-13)

- **Themes find the information strip themselves:** `fig` and `cat-fig` (slides, notes, posters)
  now cut the strip of any figure saved with `labfig`, also without a catalog `info_strip` field:
  they read the SVG and find the marker `labfig info_strip_in=0.4`, which `labfig.save` now writes
  into the PDF, SVG and PNG metadata, or, for files from v2026.10.10, the link to this repository
  in the strip. `strip: auto` is the new default of `fig`; `0pt` keeps a file whole; a catalog
  `info_strip` still wins. Files without a strip are shown as before. (PDF-only and PNG-only
  catalog entries need the field: Typst cannot search those files.)
- `scripts/propagate.sh`: after a consumer's build check, the files the check rewrote (build
  reports, "generated on" lines) are restored, so the next run does not skip that repository
  for "uncommitted changes". The tree was clean before the pull, so nothing else is touched.

## v2026.10.10 (2026-10-13)

- **Information strip below figures** (`matplotlib/labfig.py`, new): `labfig.save(fig, path,
  author=, created=, modified_by=, modified=, drive_folder=, drive_url=)` writes PDF, SVG and a
  300 dpi PNG from the same figure and adds a 0.4 in band under a dashed cut line: who made the
  figure and when, who changed it last and when, the lab-templates version and git id (linked
  to the repository; in a consumer, the upstream commit of the last subtree pull), and the Drive
  folder (name as text, linked in PDF and SVG). Cut it off in documents. `labfig.style()`
  applies the lab style (STIXGeneral where STIX Two is missing, e.g. Colab). The Drive link is
  passed in by whoever saves the figure, never stored here.
- **Themes cut the strip off:** a catalog entry with `info_strip: 0.4` is shown without its
  bottom 0.4 in by `cat-fig` (slides, notes, posters), and `fig(..., strip: 0.4in)` does it for a
  path (`themes/figure-strip.typ`, new). Entries without the field are shown whole, as before.
- **Figure versions in the file name, never overwritten:** `labfig.save(..., version=N)` writes
  `<name>-vN.pdf/.svg/.png`, shows "Version N" on the strip's first line, and refuses to write
  a version whose files exist (the error names the next free number); `draft=True` writes
  `<name>-draft.*` for work in progress. `labfig.versions(path)` lists the existing versions.
- **What made each version, kept without duplicating anything large:** the record
  `<name>-vN.yaml` (author, dates, version, template id, the script's repository and commit
  without credentials, data files with checksums, Drive folder; relative paths only), a copy of
  the script in `code/<script>-vN.py` (`code=None` for scripts in git, `code=<path>` for a
  notebook), and the **data fingerprint** (`data=[files]`, SHA-256 over names and contents;
  first 7 characters on the strip, `labfig.fingerprint()` to check data later; `data_id=` adds
  a label). `save` warns when a data file an earlier version used has changed in place.
- `docs/FIGURES_README.md`: one folder per figure with every version side by side (nothing
  overwritten, moved or renamed; replaces moving the old version into `v<N>_<date>_<name>/`,
  which older folders keep); changed data gets a new file name; a new folder only for a
  different figure; variants as `<name>-poster-vN`; `figure.yaml` keeps caption, alt text and
  topic.
- Example figure and `plot_cpi.py` saved with `labfig`, now version 3 (`…-v3.pdf/.svg/.yaml`;
  the strip is a visual change), with the data fingerprint, `info_strip: 0.4` in the catalog;
  the Colab notebook loads `labfig` from this repository and saves with it; its intro follows
  the current figure rules. `docs/FIGURES_README.md`, `docs/STYLE.md`, `README.md` describe the
  strip.

## v2026.10.9 (2026-10-13)

- Notes theme (`themes/karthein-notes.typ`), from `phys689-nucl-exp`: `notes(page: (:))` passes
  extra `set page` arguments into the theme's page setup, e.g. `page: (width: 11in, height: auto)`
  for one continuous landscape page (explicit width and height take precedence over `paper` in
  Typst); the default is unchanged.
- `scripts/propagate.sh`: the talks-repo build check compiles the newest `talks/*.group-meeting`
  deck instead of a fixed folder (talk folders are now named `YYMM.DD.<name>`, JK 2026-10-13);
  the poster theme's header comment names the renamed poster folder.
- `CLAUDE.md`: colleagues outside the lab use this repository, so a tag must not break documents
  that compiled under the previous one, and defaults stay free of lab infrastructure (lab
  behaviour opt-in); the log-book tooling to come is standalone by default.

## v2026.10.8 (2026-10-13)

- **Example figure redrawn** (`plot-us-cpi-u-yoy-2023-2026`, version 2): `plot_cpi.py` now starts
  from `karthein.mplstyle` at 6 × 4 in (15 / 13 pt), legend inside without a frame, no title or
  grid, black annotations in empty regions; PDF and SVG come from the same figure object (the
  SVG with text as outlines, so it looks the same in every Typst build). The alt text's values
  corrected (lows 2.3–2.4 %, peak about 4.2 %).
- **Figure sizes, decided:** `themes/karthein.mplstyle` now sets 15 pt bold axis labels and 13 pt
  ticks and legend at 6 × 4 in (it had 11 / 9.5 pt, against the guide and the template notebook).
  One size for slides and papers: about 12 / 11 pt beside text on a slide, 9 / 8 pt in a paper
  column. Figures drawn with the style file come out larger when redrawn.
- `docs/FIGURES_README.md`: start each script with `karthein.mplstyle` (not the `fastsims`-only
  `lab_style`); `figure.yaml` gains `version` and `variant`, and `supersedes` has one meaning;
  names may keep capitals where the name has them (FastSims, H200); coloured text uses the
  `plot_text` colours. `docs/STYLE.md` states the sizes.
- `scripts/lab-templates.sh check`: says whether a newer tag is out and how to update; never
  pulls and never fails a build (offline it says it did not check). Consumers run it first in
  every build. `pull latest` updates to the newest tag. The script now works on the repository
  root wherever it sits, so consumers use `lab/scripts/lab-templates.sh`, which every pull keeps
  current; the copy in a consumer's `scripts/` is only needed for the first `add`.
- `README.md`: the file tree as it is (exam theme, `assets/`, `propagate.sh`), what you need
  (Typst 0.15.1, packages, fonts), `<tag>` in the commands, "Staying up to date"; licence MIT
  for everything (the earlier "CC BY 4.0 for themes and documents" had no licence file).
- `assets/sources/cpi-u-yoy/`: the script and saved BLS data of the example figure, which
  `assets/catalog.yaml` pointed to but which were only in `phys206-mechanics`.
- CI: the private-material scan also reads `.ipynb`, `.json`, `.svg` and `.yml` files.
  `update-consumers.yml`: `cyclotron-talks` added.

## v2026.10.7 (2026-10-07)

- `scripts/lab-templates.sh pull` works in a repository made from `talks-repo-template`: there
  `lab/` is a plain copy without subtree history, so the first pull replaces it by the subtree
  (one commit removing the copy, then `git subtree add`); later pulls are ordinary.

## v2026.10.6 (2026-10-07)

Slide theme (`themes/karthein.typ`), requested by JK:

- **Title slide** shows what built the deck, 9.5 pt muted at the bottom right: "Template
  v2026.10.6 · git 4316cb6" — the version from `VERSION` (read relative to the theme, so
  `lab/VERSION` in a consumer) and the revision from `--input rev=` (`talks generate`, `talks
  html` and `talks course build` pass `git describe --always --dirty`; without it only the
  version is shown).
- **Justified running text**: `set par(justify: true)` for the slide body, with
  `justification-limits` (word spacing 67–130 %, tracking −0.01 to +0.02 em) so narrow columns
  do not open wide gaps; explicitly aligned content (`align(...)`: centred captions, diagram
  labels) and tables are exempt. One-line text is unaffected. A per-paragraph rule "only from
  three lines on" is not possible in Typst 0.15: bullets, composer columns and box text are not
  paragraph elements, so no show rule reaches them; two-line text is justified too. Checked on
  six decks (159 pages): no page count changed, diagrams and tables unchanged.
- `docs/STYLE.md`: justification, the **text budget** (more than 120 body words = text-heavy,
  cut by at least 10 % in the layout pass; counted by `talks layout`), the build line.

## v2026.10.5 (2026-10-05)

- `speak-math.typ`, from the instructor's review of the PHYS 206 alt texts: a function value with
  a digit reads literally, `v_x(0)` "v sub x of 0", `v^2(0)` "v of 0 squared" (no "at time zero" /
  "at point"); subscript cm/CM "center of mass"; long exponents "to the power of …, end exponent";
  a big operator whose subscript has no "=" and no upper limit reads "over" ("the sum over i of",
  "the closed integral over C of").

## v2026.10.4 (2026-10-05)

- `karthein-exam.typ` (from writing the PHYS 206 midterms and finals): `problem(source:)`, a
  "Source and changes" note shown in the key only; the key says "Solutions and grading rubric"
  in the subtitle line (the title never wraps, so the cover keeps its layout); equation-sheet
  lines sized by their bounds (display fractions no longer touch); a part's points line and its
  closing rule stay together on one page.
- `speak-math.typ`: `1\/2 g t^2` reads "one half g t squared" (a slash between small numbers is a
  spoken fraction); ∼ reads "goes like".

## v2026.10.3 (2026-10-05)

- New `themes/karthein-exam.typ`: written exams (cover page with name boxes, equation sheet and
  a graders' table computed from the parts' points; problems in parts with answer space and
  points; `mode=solutions` adds the typed solutions and green rubric marks `pts(n)[note]`).
  Example `examples/exam.typ`.
- `karthein-notes.typ`, the class script (one document per class meeting): `say` (italic in the
  lecture copy, prose in the student copy), `write(min:)`/`draw(min:)` frames, `cue` (lecture
  copy only), `recap(min:)`, `quiz(yaml, only:)` (answers on the next page in the lecture copy;
  `feedback: true` questions print none), `work`/`sketch` with `min:`; `notes(chapter:, week:,
  day:, budget:, plan:)` prints the meeting line, the writing total against the budget and the
  time plan; the git revision from `--input rev=` on the first page; demo panels show their
  explanation in the lecture copy and "What happens" in the student copy; `aside`, `sketch`,
  `demo`, `poll`, `work(title:)` (from the PHYS 206 lectures).
- `speak-math.typ`: many readings for mechanics (work labels "W done by gravity", `W^N`, unit
  vectors, `·`/`×` between vectors as dot/cross incl. brackets and magnitude bars, limits,
  `v^2(0)` "at time zero", `max`/`min` subscripts, ⟂/∥, American unit spellings, …).
- New consumer `cyclotron-talks` (notes theme: host guidelines) in `scripts/propagate.sh` and CLAUDE.md.


## v2026.10.2 (2026-10-03)

- CLAUDE.md and the CI scan: the lab's public contact address may appear; the scan checks home-folder and Drive-mirror prefixes and key patterns.
- LOGBOOK_GUIDE: log books compile from the repository root (`typst compile --root . notes/<name>-logbook.typ`), since the template is reached through a shim into `lab/`.

## v2026.10.1 (2026-10-02)

First version, assembled from the canonical copies in `talks-repo` (themes, STYLE, COURSES),
`fastsims` (lab-notebook template, LOGBOOK_GUIDE, FIGURES_README) and `karthein-cv`
(`cv-theme.typ`):

- `themes/karthein.typ` (Touying slides), `karthein-poster.typ`, `karthein-notes.typ`
  (student / lecture / solutions modes), `cv-theme.typ`, `tokens.typ` (shared palette, panels,
  radii, shadows; all themes import it), `speak-math.typ` (spoken alt text, `apply-alts`).
- Logo paths in the slide theme are root-relative (`/themes/logos/...`): the consumer's logos
  stay where they are when the theme lives in `lab/`.
- `notes/labnotes-template.typ`, `docs/*.md`, `matplotlib/KartheinLab-figure-template.ipynb`.
- `examples/` compile under PDF/UA-1 in CI; `scripts/lab-templates.sh` for consumers;
  `scripts/sync_drive.py` for the Drive copies.
