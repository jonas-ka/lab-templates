"""Lab figure helpers: the lab style, and saving versioned figures with an information strip.

    import sys; sys.path.insert(0, "lab/matplotlib")      # lab-templates as a subtree in lab/
    import labfig
    labfig.style()                                        # themes/karthein.mplstyle
    fig, ax = plt.subplots()                              # 6 x 4 in from the style
    ...
    labfig.save(fig, "Figures/plot-x/plot-x", version=1, author="A. Author", created="2026-10-13",
                data=["Figures/plot-x/data/plot-x.csv"],
                drive_folder="Figures/plot-x", drive_url="<the folder's share link>")
    # -> Figures/plot-x/plot-x-v1.pdf, .svg, .png   the figure
    #    Figures/plot-x/plot-x-v1.yaml              its record
    #    Figures/plot-x/code/<script>-v1.py         the script that drew it

`save` writes PDF, SVG and PNG (300 dpi) from the same figure object, named `<name>-v<N>.<ext>`.
**A version is never overwritten:** if a file of that version exists, `save` stops and names
the next free number; every visual change of the figure, and every change of its data, is a new
version. While working on a figure, `draft=True` writes `<name>-draft.<ext>`, which may be
overwritten (no record, no code copy).

With each version it keeps what made it, without duplicating anything large:
- **the record** `<name>-v<N>.yaml`: author, dates, version, the lab-templates version, the
  script's repository and commit, the data files and their fingerprint, the Drive folder;
- **the script**, copied to `code/<script>-v<N>.py` (a few kB; `code=None` skips the copy,
  `code=<path>` copies another file, e.g. a notebook);
- **the data fingerprint**: a SHA-256 checksum over the files given as `data=` (names and
  contents; folders included). Identical data gives the same fingerprint, any change a
  different one, so it shows which versions share data and verifies data found later
  (`labfig.fingerprint(paths)`). The data itself is not copied: the plotted data goes in the
  figure folder's `data/` once, raw data too large for Drive stays where it is (`data/WHERE.md`).
  `data_id=` adds a label (or replaces the fingerprint for data too large to read each time).

Below the figure it adds an **information strip** of fixed height (`STRIP_IN`, bottom of the
file), under a dashed cut line: who made the figure and when, who changed it last and when, the
version; the lab-templates version and git id it was made with (linked to the repository), the
data fingerprint, and the Drive folder (the name as text, linked in PDF and SVG; a PNG keeps
only the text). Cut the strip off when the figure goes into a paper, talk or poster: crop the
bottom `STRIP_IN` inches, or let the lab themes do it: they find the strip by the marker
"labfig info_strip_in=0.4" that `save` writes into the PDF, SVG and PNG metadata (or by a
catalog field `info_strip: 0.4`). `info=False` saves without the strip.

The Drive link is passed in by whoever saves the figure; it never belongs in lab-templates
(public). Records hold no absolute paths (paths relative to the figure folder or the script's
repository). Works without the lab: everything except `version` (or `draft`), `author` and
`created` is optional.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import warnings
from datetime import date, datetime
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.backends.backend_agg import RendererAgg
from matplotlib.lines import Line2D
from matplotlib.textpath import TextToPath
from matplotlib.transforms import Bbox

ROOT = Path(__file__).resolve().parents[1]          # lab-templates, or a consumer's lab/
STYLE = ROOT / "themes" / "karthein.mplstyle"
REPO = os.environ.get("LAB_TEMPLATES_URL", "https://github.com/jonas-ka/lab-templates.git").removesuffix(".git")

STRIP_IN = 0.40        # height of the information strip (inches, at the saved size)
PAD_IN = 0.05          # white margin around the figure, as bbox_inches="tight" would add
TEXT_PT = 7.0          # strip text size; shrunk if a line is wider than the figure
MUTED, LINK, CUT = "#333333", "#007682", "#B0B0B0"   # palette.yaml: muted, link_text; cut line
_TEXT_TO_PATH = TextToPath()


def style() -> None:
    """Apply the lab style (STIX Two Text; STIXGeneral, which ships with matplotlib, where the
    STIX Two fonts are not installed, e.g. on Colab)."""
    plt.style.use(STYLE)
    names = {f.name for f in font_manager.fontManager.ttflist}
    if "STIX Two Text" not in names:
        plt.rcParams["font.family"] = "STIXGeneral"


def _git(*args: str, cwd: Path = ROOT) -> str | None:
    try:
        r = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def _public_url(url: str | None) -> str | None:
    """A remote URL without credentials (https://user:token@host/... -> https://host/...)."""
    return re.sub(r"(?<=//)[^/@]+@", "", url).removesuffix(".git") if url else None


def template_id() -> dict[str, str | None]:
    """The lab-templates version and commit these helpers come from, and a link to it.

    In lab-templates itself (or a clone, e.g. on Colab): the checked-out commit, `-dirty` when
    tracked files under it are changed. In a consumer (subtree in lab/): the upstream commit
    recorded by the last subtree pull. Otherwise the version alone.
    """
    version = (ROOT / "VERSION").read_text().strip() if (ROOT / "VERSION").exists() else None
    commit, full = None, None
    top = _git("rev-parse", "--show-toplevel")
    if top and Path(top).resolve() == ROOT:
        full = _git("rev-parse", "HEAD")
        if full:
            commit = full[:7] + ("-dirty" if _git("status", "--porcelain", "--untracked-files=no", "--", ".") else "")
    elif top:
        prefix = ROOT.relative_to(Path(top).resolve()).as_posix()
        msg = _git("log", "-1", f"--grep=git-subtree-dir: {prefix}", "--format=%B") or ""
        m = re.search(r"git-subtree-split:\s*([0-9a-f]{7,40})", msg)
        if m:
            full = m.group(1)
            commit = full[:7]
    ref = full or version
    return {"version": version, "commit": commit, "url": f"{REPO}/tree/{ref}" if ref else REPO}


def script_id(script: str | Path) -> dict[str, str | None]:
    """Where a script lives in git: repository (without credentials), commit (`-dirty` when the
    script has uncommitted changes) and its path in the repository. Name only outside git."""
    script = Path(script).resolve()
    top = _git("rev-parse", "--show-toplevel", cwd=script.parent)
    if not top:
        return {"file": script.name, "repository": None, "commit": None}
    commit = _git("rev-parse", "HEAD", cwd=script.parent)
    if commit and _git("status", "--porcelain", "--", script.name, cwd=script.parent):
        commit += "-dirty"
    return {"file": script.relative_to(Path(top).resolve()).as_posix(),
            "repository": _public_url(_git("remote", "get-url", "origin", cwd=script.parent)),
            "commit": commit}


def _calling_script() -> Path | None:
    """The script being run (`python plot_x.py`); None in a notebook or an interactive session."""
    f = getattr(sys.modules.get("__main__"), "__file__", None)
    return Path(f).resolve() if f and Path(f).suffix == ".py" and Path(f).exists() else None


def _data_files(paths: list[str | Path]) -> list[tuple[str, Path]]:
    """(name, file) for every file in `paths`, folders walked; names are the file name, or
    folder/inner path, so the fingerprint does not depend on where the data sits."""
    out = []
    for p in map(Path, paths):
        if p.is_dir():
            out += [(f"{p.name}/{f.relative_to(p).as_posix()}", f) for f in sorted(p.rglob("*"))
                    if f.is_file() and not any(part.startswith(".") for part in f.relative_to(p).parts)]
        elif p.is_file():
            out.append((p.name, p))
        else:
            raise FileNotFoundError(f"data not found: {p}")
    return sorted(out)


def fingerprint(paths: list[str | Path] | str | Path) -> str:
    """SHA-256 over the names and contents of the files in `paths` (folders included): the same
    data gives the same value. The strip shows the first 7 characters."""
    paths = [paths] if isinstance(paths, (str, Path)) else paths
    h = hashlib.sha256()
    for name, f in _data_files(paths):
        h.update(name.encode() + b"\0" + str(f.stat().st_size).encode() + b"\0")
        with open(f, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
    return h.hexdigest()


def _file_sha(f: Path) -> str:
    h = hashlib.sha256()
    with open(f, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _check_data_unchanged(path: Path, files: dict[str, str]) -> None:
    """Warn when a data file an earlier version used has changed since (data is never
    overwritten either: changed data goes in under a new name, so every version keeps its own)."""
    for v in versions(path):
        rec = path.parent / f"{path.name}-v{v}.yaml"
        if not rec.exists():
            continue
        for line in rec.read_text(encoding="utf-8").splitlines():
            if line.startswith("data: "):
                for entry in json.loads(line[6:]).get("files", []):
                    if isinstance(entry, dict) and entry.get("path") in files and files[entry["path"]] != entry.get("sha256"):
                        warnings.warn(f"{entry['path']} has changed since version {v} used it; version {v}'s data is "
                                      "gone. Changed data goes in under a new file name.", stacklevel=3)


def _day(d: str | date | None) -> str | None:
    return d.isoformat() if isinstance(d, date) else d


def _rel(p: Path, base: Path) -> str:
    """`p` relative to `base` (never an absolute path in a record)."""
    return Path(os.path.relpath(Path(p).resolve(), base.resolve())).as_posix()


def _add_strip(fig, box: Bbox, lines: list[list[tuple[str, str | None]]], raster_dpi: float | None = None) -> list:
    """Draw the cut line and the strip text in the band below `box` (inches); return the artists.

    Text widths: the font's metrics for PDF and SVG; for a PNG (`raster_dpi`), the raster
    renderer at that resolution, which sets glyphs slightly wider.
    """
    # Figure-fraction coordinates (inches / figure size): savefig with a custom bbox shifts
    # transFigure along with the crop, but not dpi_scale_trans.
    fw, fh = fig.get_size_inches()
    x0, width, top = box.x0, box.width, box.y0
    artists = [fig.add_artist(Line2D([x0 / fw, (x0 + width) / fw], [(top - 0.03) / fh] * 2,
                                     transform=fig.transFigure, color=CUT, lw=0.5, ls=(0, (4, 3))))]

    # Each piece is its own text (a link covers one whole text); neighbouring pieces without a
    # link are joined. Packing boxes (offsetbox) would lay the pieces out per format, but they
    # do not follow savefig's custom bbox, so plain figure texts are placed by measured widths.
    rows = []
    for segments in lines:
        out: list[tuple[str, str | None]] = []
        for text, url in segments:
            if out and url is None and out[-1][1] is None:
                out[-1] = (out[-1][0] + text, None)
            else:
                out.append((text, url))
        rows.append(out)
    prop = font_manager.FontProperties(family=plt.rcParams["font.family"])

    raster = RendererAgg(10, 10, raster_dpi) if raster_dpi else None

    def inches(text: str, size: float) -> float:
        p = prop.copy()
        p.set_size(size)
        if raster:
            return raster.get_text_width_height_descent(text, p, ismath=False)[0] / raster_dpi
        return _TEXT_TO_PATH.get_text_width_height_descent(text, p, ismath=False)[0] / 72

    size = TEXT_PT
    for _ in range(5):                   # too wide for the figure: smaller, for all lines alike
        wide = max(sum(inches(t, size) for t, _ in row) for row in rows)
        if wide <= width - 0.04:
            break
        size *= 0.99 * (width - 0.04) / wide
    for i, row in enumerate(rows):
        x, y = x0 + 0.02, top - 0.17 - i * 0.15
        for text, url in row:
            artists.append(fig.text(x / fw, y / fh, text, transform=fig.transFigure, fontsize=size,
                                    color=LINK if url else MUTED, ha="left", va="baseline", url=url))
            x += inches(text, size)
    return artists


def versions(path: str | Path) -> list[int]:
    """The versions of figure `path` (`<name>-v<N>.*` next to it) that exist, in order."""
    path = Path(path)
    pat = re.compile(re.escape(path.name) + r"-v(\d+)\.[A-Za-z0-9]+$")
    found = {int(m.group(1)) for f in path.parent.glob(path.name + "-v*") if (m := pat.match(f.name))}
    return sorted(found)


def _record_text(fields: dict) -> str:
    """The record as YAML: one key per line, values in JSON notation (which YAML reads)."""
    lines = ["# Written by labfig.save (lab-templates matplotlib/labfig.py). Never edited or overwritten:",
             "# a changed figure is the next version, with its own record."]
    lines += [f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in fields.items() if v not in (None, [], {})]
    return "\n".join(lines) + "\n"


def save(fig, path: str | Path, *, version: int | None = None, draft: bool = False,
         author: str, created: str | date,
         modified_by: str | None = None, modified: str | date | None = None,
         data: list[str | Path] | str | Path | None = None, data_id: str | None = None,
         code: str | Path | None = "auto", code_dir: str | Path | None = None,
         drive_folder: str | None = None, drive_url: str | None = None,
         formats: tuple[str, ...] = ("pdf", "svg", "png"), info: bool = True,
         svg_text: str = "path") -> Path:
    """Save `fig` as `<path>-v<version>.pdf/.svg/.png` with the information strip below it, plus
    the record `<path>-v<version>.yaml` and a copy of the script in `code/`.

    version: the figure's version, 1 for a new figure, one more for every visual change and every
        data change. An existing version is never overwritten: `save` raises FileExistsError.
    draft: save as `<path>-draft.<ext>` (overwritten freely; the strip says "Draft"; no record,
        no code copy).
    author, created: who made the figure and when (keep the original date in later versions).
    modified_by, modified: who changed it last and when (shown when given).
    data: the input files or folders; their fingerprint goes on the strip and in the record.
    data_id: a label for the data (e.g. a run or job number), shown with the fingerprint, or
        instead of it when `data` is not given.
    code: "auto" copies the running script; a path copies that file (e.g. a notebook); None
        copies nothing (for a script already in git). The script's repository and commit go in
        the record either way.
    code_dir: where the copy goes (default: `code/` next to the figure), as `<stem>-v<N><ext>`.
    drive_folder, drive_url: the Drive folder the figure lives in (name shown as text; the link
        is embedded in PDF and SVG). Leave out when the figure is not on Drive.
    svg_text: "path" draws SVG text as outlines (looks the same wherever it is rendered, e.g.
        in Typst); "text" keeps it editable. The PDF always keeps editable text.
    Returns the saved path without suffix (`<path>-v<version>` or `<path>-draft`).
    """
    path = Path(path)
    folder = path.parent
    # the script that drew the figure: recorded always (repository, commit); copied unless code=None
    script = Path(code) if code not in ("auto", None) else _calling_script()
    if draft:
        stem, tag = f"{path.name}-draft", "Draft"
        copy_to = None
    else:
        if not isinstance(version, int) or version < 1:
            raise ValueError("give the figure's version (version=1 for a new figure), or draft=True while working on it")
        stem, tag = f"{path.name}-v{version}", f"Version {version}"
        copy_to = ((Path(code_dir) if code_dir else folder / "code") / f"{script.stem}-v{version}{script.suffix}"
                   if script and code is not None else None)
        targets = [folder / f"{stem}.{ext}" for ext in (*formats, "yaml")] + ([copy_to] if copy_to else [])
        taken = [t for t in targets if t.exists()]
        if taken:
            nxt = max(versions(path) + [version]) + 1
            raise FileExistsError(f"{taken[0].name} exists; a version is never overwritten. A changed figure "
                                  f"is version {nxt} (version={nxt}), or use draft=True while working on it.")
    out = folder / stem
    folder.mkdir(parents=True, exist_ok=True)

    data_list = [data] if isinstance(data, (str, Path)) else list(data or [])
    fp = fingerprint(data_list) if data_list else None
    data_files = {_rel(f, folder): _file_sha(f) for _, f in _data_files(data_list)} if data_list else {}
    if data_files and not draft:
        _check_data_unchanged(path, data_files)
    tid = template_id()
    fig.canvas.draw()
    content = fig.get_tightbbox(fig.canvas.get_renderer()).padded(PAD_IN)
    if info:
        line1 = [(f"Created {_day(created)} by {author}", None)]
        if modified or modified_by:
            line1.append((" · Modified " + " by ".join(filter(None, [_day(modified), modified_by])), None))
        line1.append((f" · {tag}", None))
        label = "lab-templates " + ", git ".join(filter(None, [tid["version"], tid["commit"]]))
        line2 = [("Template: ", None), (label, tid["url"])]
        if fp or data_id:
            line2.append((" · Data: " + " ".join(filter(None, [fp[:7] if fp else None,
                                                               f"({data_id})" if fp and data_id else data_id])), None))
        if drive_folder:
            line2 += [(" · Drive: ", None), (drive_folder, drive_url)]
        box = Bbox.from_extents(content.x0, content.y0 - STRIP_IN, content.x1, content.y1)
    else:
        box = content
    for ext in formats:
        dpi = 300 if ext == "png" else None
        artists = _add_strip(fig, content, [line1, line2], raster_dpi=dpi) if info else []
        try:
            with plt.rc_context({"svg.fonttype": "path" if svg_text == "path" else "none"}):
                # the marker lets the lab themes find (and cut) the strip in any copy of the file
                meta = {"Keywords": f"labfig info_strip_in={STRIP_IN}"} if info else {}
                fig.savefig(folder / f"{stem}.{ext}", bbox_inches=box, metadata=meta, **({"dpi": dpi} if dpi else {}))
        finally:
            for a in artists:
                a.remove()
    if draft:
        return out

    if copy_to:
        copy_to.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(script, copy_to)
    sid = script_id(script) if script else None
    _record = {
        "figure": path.name, "version": version, "files": [f"{stem}.{ext}" for ext in formats],
        "created": _day(created), "author": author, "modified": _day(modified), "modified_by": modified_by,
        "saved": datetime.now().astimezone().isoformat(timespec="seconds"),
        "template": tid,
        "code": {**sid, "copy": _rel(copy_to, folder) if copy_to else None} if sid else None,
        "data": {"fingerprint": f"sha256:{fp}" if fp else None, "id": data_id,
                 "files": [{"path": k, "sha256": v} for k, v in data_files.items()]} if (fp or data_id) else None,
        "drive": {"folder": drive_folder, "url": drive_url} if drive_folder else None,
        "info_strip_in": STRIP_IN if info else None,
    }
    (folder / f"{stem}.yaml").write_text(_record_text(_record), encoding="utf-8")
    return out
