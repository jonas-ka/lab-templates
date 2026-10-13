"""What later entries say about earlier ones, computed from the whole book (never written into
the old files): resolutions, corrections, redactions, related links and backlinks."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from .entry import OPENABLE, Entry


@dataclass
class State:
    resolved_by: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))   # "id#anchor" -> resolver ids
    corrected_by: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    redacted_by: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    related: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))          # both directions
    backlinks: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))        # [[id]] in text

    def open_items(self, entries: dict[str, Entry]) -> list[tuple[Entry, str, str]]:
        """(entry, anchor, block name) for every issue/todo with an id that nothing resolves yet."""
        out = []
        for e in sorted(entries.values(), key=lambda x: x.id):
            for b in e.blocks:
                if b.name in OPENABLE and b.anchor and not self.resolved_by.get(f"{e.id}#{b.anchor}"):
                    out.append((e, b.anchor, b.name))
        return out


def compute(entries: dict[str, Entry], exclude: set[str] = frozenset()) -> State:
    """State from all entries except those in `exclude` (the ones being checked, so that an
    entry does not count as already resolving what it resolves)."""
    s = State()
    for e in entries.values():
        if e.id in exclude:
            continue
        h = e.header
        for target in h.get("resolves") or []:
            s.resolved_by[target].append(e.id)
        if h.get("corrects"):
            s.corrected_by[h["corrects"]].append(e.id)
        if h.get("redacts"):
            s.redacted_by[h["redacts"]].append(e.id)
        for r in h.get("related") or []:
            s.related[e.id].add(r)
            s.related[r].add(e.id)
        for target, _ in e.links():
            if not target.startswith("wiki:"):
                s.backlinks[target.split("#")[0]].add(e.id)
    return s
