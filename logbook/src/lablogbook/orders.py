"""Purchases in the log book. An order is an entry of kind `order` whose header lists its items;
every item that has not arrived is an open item (`::: todo {#item-N priority=low}`) until a later
entry resolves it ("Resolve" in the view, or `resolves:`). `status()` is what the view's
Purchases page and the status file (`logbook orders --json`) show."""

from __future__ import annotations

import json
import re

from . import state as state_mod
from .book import Book

KIND = "order"
NUMBERS = ("qty", "unit_cost", "total")


def anchor(n: int) -> str:
    return f"item-{n}"


def _num(v):
    """A number as written in a sheet ("$1,234.50", 3.0) → 1234.5, 3; text that is not a number stays text."""
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return int(v) if float(v).is_integer() else v
    s = re.sub(r"[,$€£\s]", "", str(v))
    try:
        f = float(s)
    except ValueError:
        return str(v).strip()
    return int(f) if f.is_integer() else f


def normalise(items: list) -> list[dict]:
    """Items as the header keeps them: n (1, 2, … unless given), item, qty, unit_cost, total,
    info, ordered, and arrived (true, or the date) for one that has already arrived."""
    out = []
    for i, it in enumerate(items or [], start=1):
        x = {"n": int(it.get("n") or i), "item": str(it.get("item") or "").strip()}
        for k in NUMBERS:
            v = _num(it.get(k))
            if v is not None:
                x[k] = v
        for k in ("info", "ordered"):
            if it.get(k) not in (None, ""):
                x[k] = str(it[k]).strip()
        if it.get("arrived"):
            x["arrived"] = it["arrived"] if isinstance(it["arrived"], str) else True
        out.append(x)
    return out


def parse_items(text: str) -> list[dict]:
    """Items from a JSON list, as a form's "Items" section carries them (a ```json block or bare)."""
    t = re.sub(r"^```\w*\s*|\s*```\s*$", "", (text or "").strip())
    data = json.loads(t) if t else []
    if not isinstance(data, list):
        raise ValueError("Items: a JSON list of {item, qty, unit_cost, total, info, ordered}")
    return normalise(data)


def money(v, symbol: str = "$") -> str:
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        s = f"{abs(v):,.2f}"
        return ("−" if v < 0 else "") + symbol + (s[:-3] if s.endswith(".00") else s)
    return "" if v is None else str(v)


def _cell(v) -> str:
    s = "" if v is None else str(v)
    if isinstance(v, float) and v.is_integer():
        s = str(int(v))
    return s.replace("|", "\\|").replace("\n", " ").strip()


def body(items: list[dict], intro: str = "", symbol: str = "$") -> str:
    """The entry's text: an optional introduction, the table of items, and one open item for
    every item that has not arrived."""
    rows = ["| # | Item | Qty | Unit cost | Total | Quote / info | Ordered |",
            "|---:|---|---:|---:|---:|---|---|"]
    for x in items:
        info = x.get("info", "")
        info = f"<{info}>" if re.match(r"^https?://\S+$", info) else _cell(info)
        rows.append("| " + " | ".join([str(x["n"]), _cell(x["item"]), _cell(x.get("qty")),
                                        money(x.get("unit_cost"), symbol), money(x.get("total"), symbol),
                                        info, _cell(x.get("ordered"))]) + " |")
    parts = [intro.strip()] if intro and intro.strip() else []
    parts.append("\n".join(rows))
    waiting = [x for x in items if not x.get("arrived")]
    if waiting:
        parts.append("Each item stays open until a later entry says it arrived (\"Resolve\" on the item in the view).")
        for x in waiting:
            qty = f" (×{_cell(x['qty'])})" if x.get("qty") not in (None, "", 1) else ""
            parts.append(f"::: todo {{#{anchor(x['n'])} priority=low}}\nArrived: {_cell(x['item'])}{qty}\n:::")
    return "\n\n".join(parts) + "\n"


def status(book: Book, st: state_mod.State | None = None) -> list[dict]:
    """Every item of every order, the newest order first: its order, entry, fields, and status
    "open" or "arrived" (with the date, entry and authors of the entry that said so, when one did)."""
    st = st or state_mod.compute(book.entries)
    out = []

    def newest_first(e):
        n = _num(e.header.get("order"))
        return (0, -n, "") if isinstance(n, (int, float)) else (1, "", e.date)   # numbered orders first

    for e in sorted(book.entries.values(), key=newest_first):
        if e.header.get("kind") != KIND:
            continue
        for x in normalise(e.header.get("items") or []):
            key = f"{e.id}#{anchor(x['n'])}"
            row = {"order": str(e.header.get("order", "")), "entry": e.id, "key": key, **x}
            by = st.resolved_by.get(key) or []
            if x.get("arrived"):
                row["status"] = "arrived"
                if isinstance(x["arrived"], str):
                    row["arrived_on"] = x["arrived"]
            elif by and by[0] in book.entries:
                r = book.entries[by[0]]
                row.update(status="arrived", arrived_on=r.date, arrived_in=r.id, arrived_by=r.authors)
            else:
                row["status"] = "open"
            row.pop("arrived", None)
            out.append(row)
    return out
