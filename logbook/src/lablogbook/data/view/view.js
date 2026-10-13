/* The log-book view: everything runs in the browser over the data embedded in the page. */
(function () {
  "use strict";
  const D = JSON.parse(document.getElementById("lb-data").textContent);
  const E = D.entries.slice().sort((a, b) => (a.date + (a.time || "") + a.id).localeCompare(b.date + (b.time || "") + b.id));
  const byId = Object.fromEntries(E.map((e) => [e.id, e]));
  const wikiBy = Object.fromEntries(D.wiki.map((w) => [w.page, w]));
  const refBy = Object.fromEntries(D.references.map((r) => [r.key, r]));
  const $ = (s, el = document) => el.querySelector(s);
  const main = $("#main"), filtersEl = $("#filters"), layout = $(".layout");

  // ------------------------------------------------------------------ helpers -------------
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const norm = (s) => String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[−–]/g, "-").toLowerCase();
  const name = (h) => (D.people[h] && D.people[h].name) || h;
  const enc = encodeURIComponent;
  const days = (a, b) => Math.round((Date.parse(b) - Date.parse(a)) / 864e5);
  const fmtLogged = (s) => {
    if (!s) return "not yet logged";
    const d = new Date(s);
    return isNaN(d) ? "logged " + s : "logged " + d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
  };
  const withText = (w) => (w ? " (with assistance from " + (w === "claude" ? "Claude Code" : w) + ")" : "");
  const entryLink = (id, anchor, text) => {
    const e = byId[id];
    const t = text || (e ? e.title : id) + (anchor ? " (#" + anchor + ")" : "");
    return e ? `<a href="#/e/${enc(id)}${anchor ? "/" + enc(anchor) : ""}">${esc(t)}</a>` : `<span title="${esc(id)}">${esc(t)}</span>`;
  };
  const projectsOf = (e) => [e.project].concat(e.also || []);
  for (const e of E) {
    e._title = norm(e.title);
    e._hay = norm([e.id, e.title, e.text, e.kind, e.project, e.subproject, (e.also || []).join(" "), (e.apparatus || []).join(" "),
      (e.tags || []).join(" "), e.authors.map(name).join(" "), e.authors.join(" "), (e.runs || []).join(" "),
      (e.parameters || []).map((p) => `${p.name} ${p.value} ${p.unit || ""}`).join(" "),
      (e.epics || []).map((s) => s.group + " " + s.pvs.map((p) => `${p.name} ${p.value} ${p.unit || ""}`).join(" ")).join(" "),
      (e.attendees || []).map(name).join(" ")].join(" "));
  }

  // ------------------------------------------------------------------ filters -------------
  const F = { q: "", project: new Set(), sub: new Set(), who: new Set(), app: new Set(), kind: new Set(), tag: new Set(),
              from: "", to: "", open: false, figs: false, release: false, sort: "new" };
  const SETS = ["project", "sub", "who", "app", "kind", "tag"];
  const FIELDS = new Set(["kind", "project", "by", "tag", "on"]);   // kind:run project:fast by:aa tag:x on:source
  function parseQuery(q) {
    const terms = [], fields = {};
    const re = /(\w+):("[^"]*"|\S+)|"([^"]*)"|(\S+)/g;
    let m;
    while ((m = re.exec(q))) {
      if (m[1] && FIELDS.has(m[1].toLowerCase())) fields[m[1].toLowerCase()] = norm(m[2].replace(/"/g, ""));
      else terms.push(norm(m[1] ? m[0].replace(/"/g, "") : m[3] != null ? m[3] : m[4]));   // e.g. a PV name SRC:Extract
    }
    return { terms: terms.filter(Boolean), fields };
  }
  function openCount(e) { return Object.values(e.resolved || {}).filter((r) => !r.length).length; }
  function match(e, Q) {
    if (F.project.size && !projectsOf(e).some((p) => F.project.has(p))) return false;
    if (F.sub.size && !F.sub.has(e.project + "/" + (e.subproject || ""))) return false;
    if (F.who.size && !e.authors.some((a) => F.who.has(a))) return false;
    if (F.app.size && !(e.apparatus || []).some((a) => F.app.has(a))) return false;
    if (F.kind.size && !F.kind.has(e.kind)) return false;
    if (F.tag.size && !(e.tags || []).some((t) => F.tag.has(t))) return false;
    if (F.from && e.date < F.from) return false;
    if (F.to && e.date > F.to) return false;
    if (F.open && !openCount(e)) return false;
    if (F.figs && !e.figures) return false;
    if (F.release && e.release !== "candidate") return false;
    const f = Q.fields;
    if (f.kind && norm(e.kind) !== f.kind) return false;
    if (f.project && !projectsOf(e).some((p) => norm(p).includes(f.project))) return false;
    if (f.by && !e.authors.some((a) => norm(a) === f.by || norm(name(a)).includes(f.by))) return false;
    if (f.tag && !(e.tags || []).some((t) => norm(t) === f.tag)) return false;
    if (f.on && !(e.apparatus || []).some((a) => norm(a) === f.on)) return false;
    return Q.terms.every((t) => e._hay.includes(t));
  }
  function score(e, Q) { return Q.terms.reduce((s, t) => s + (e._title.includes(t) ? 3 : 1), 0); }
  function filtered() {
    const Q = parseQuery(F.q);
    let list = E.filter((e) => match(e, Q));
    if (Q.terms.length && F.sort === "relevance") list.sort((a, b) => score(b, Q) - score(a, Q));
    else if (F.sort === "old") list = list.slice();
    else list = list.slice().reverse();
    return { list, Q };
  }
  function anyFilter() { return F.q || SETS.some((k) => F[k].size) || F.from || F.to || F.open || F.figs || F.release; }
  function toHash() {
    const p = new URLSearchParams();
    if (F.q) p.set("q", F.q);
    for (const k of SETS) if (F[k].size) p.set(k, [...F[k]].join("|"));
    for (const k of ["from", "to"]) if (F[k]) p.set(k, F[k]);
    for (const k of ["open", "figs", "release"]) if (F[k]) p.set(k, "1");
    if (F.sort !== "new") p.set("sort", F.sort);
    const s = p.toString();
    return s ? "?" + s : "";
  }
  function fromHash(qs) {
    const p = new URLSearchParams(qs || "");
    F.q = p.get("q") || "";
    for (const k of SETS) F[k] = new Set((p.get(k) || "").split("|").filter(Boolean));
    F.from = p.get("from") || ""; F.to = p.get("to") || "";
    F.open = p.has("open"); F.figs = p.has("figs"); F.release = p.has("release");
    F.sort = p.get("sort") || "new";
    $("#q").value = F.q;
  }

  function count(fn) {
    const c = {};
    for (const e of E) for (const k of fn(e)) c[k] = (c[k] || 0) + 1;
    return c;
  }
  function checkbox(set, value, label, n, cls = "") {
    return `<label class="${cls}"><input type="checkbox" data-set="${set}" value="${esc(value)}" ${F[set].has(value) ? "checked" : ""}>` +
      `<span>${esc(label)}</span><span class="n">${n}</span></label>`;
  }
  let showAllTags = false;
  function renderFilters() {
    const pc = count(projectsOf), sc = count((e) => (e.subproject ? [e.project + "/" + e.subproject] : []));
    const wc = count((e) => e.authors), ac = count((e) => e.apparatus || []), kc = count((e) => [e.kind]), tc = count((e) => e.tags || []);
    let h = "<h3>Projects</h3>";
    for (const p of D.projects) {
      if (!pc[p.name]) continue;
      h += checkbox("project", p.name, p.name, pc[p.name]);
      for (const s of p.subprojects) if (sc[p.name + "/" + s]) h += checkbox("sub", p.name + "/" + s, s, sc[p.name + "/" + s], "sub");
    }
    h += "<h3>People</h3>" + Object.keys(wc).sort((a, b) => name(a).localeCompare(name(b))).map((w) => checkbox("who", w, name(w), wc[w])).join("");
    if (Object.keys(ac).length) h += "<h3>Apparatus</h3>" + D.apparatus.filter((a) => ac[a.id]).map((a) => checkbox("app", a.id, a.name, ac[a.id])).join("");
    h += "<h3>Kind</h3>" + Object.keys(kc).sort().map((k) => checkbox("kind", k, k, kc[k])).join("");
    const tags = Object.keys(tc).sort((a, b) => tc[b] - tc[a] || a.localeCompare(b));
    if (tags.length) {
      h += "<h3>Tags</h3>" + tags.slice(0, showAllTags ? tags.length : 12).map((t) => checkbox("tag", t, t, tc[t])).join("");
      if (tags.length > 12) h += `<button class="more" data-act="tags">${showAllTags ? "fewer tags" : "all " + tags.length + " tags"}</button>`;
    }
    h += `<h3>Dates</h3><label for="f-from" class="sr">From</label><input id="f-from" type="date" value="${esc(F.from)}" data-date="from" aria-label="From">` +
      `<label for="f-to" class="sr">To</label><input id="f-to" type="date" value="${esc(F.to)}" data-date="to" aria-label="To">`;
    h += "<h3>Only</h3>" +
      `<label><input type="checkbox" data-flag="open" ${F.open ? "checked" : ""}><span>with open items</span></label>` +
      `<label><input type="checkbox" data-flag="figs" ${F.figs ? "checked" : ""}><span>with figures</span></label>` +
      `<label><input type="checkbox" data-flag="release" ${F.release ? "checked" : ""}><span>release candidates</span></label>`;
    if (anyFilter()) h += `<button class="btn clear" data-act="clear">Clear all filters</button>`;
    filtersEl.innerHTML = h;
  }
  filtersEl.addEventListener("change", (ev) => {
    const t = ev.target;
    if (t.dataset.set) { t.checked ? F[t.dataset.set].add(t.value) : F[t.dataset.set].delete(t.value); }
    else if (t.dataset.date) F[t.dataset.date] = t.value;
    else if (t.dataset.flag) F[t.dataset.flag] = t.checked;
    go(currentList());
  });
  filtersEl.addEventListener("click", (ev) => {
    const a = ev.target.dataset.act;
    if (a === "clear") { fromHash(""); go(currentList()); }
    if (a === "tags") { showAllTags = !showAllTags; renderFilters(); }
  });
  const currentList = () => (route().name === "open" ? "#/open" : "#/");
  function go(base) { const h = base + toHash(); if (location.hash !== h) location.hash = h; else render(); }

  // ------------------------------------------------------------------ pieces --------------
  function highlight(text, terms) {
    let s = esc(text);
    for (const t of terms) {
      if (t.length < 2) continue;
      const re = new RegExp("(" + t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + ")", "ig");
      s = s.replace(re, "<mark>$1</mark>");
    }
    return s;
  }
  function snippet(e, terms) {
    const text = e.text || "";
    let at = 0;
    if (terms.length) { const i = norm(text).indexOf(terms[0]); if (i > 60) at = i - 60; }
    const s = (at ? "… " : "") + text.slice(at, at + 230) + (text.length > at + 230 ? " …" : "");
    return highlight(s, terms);
  }
  function chips(e) {
    let h = `<span class="chip kind kind-${esc(e.kind)}">${esc(e.kind)}</span>`;
    h += `<a class="chip project" href="#/project/${enc(e.project)}">${esc(e.project)}${e.subproject ? " · " + esc(e.subproject) : ""}</a>`;
    for (const a of e.also || []) h += ` <a class="chip project" href="#/project/${enc(a)}">${esc(a)}</a>`;
    const oc = openCount(e);
    if (oc) h += ` <span class="chip open">${oc} open</span>`;
    if (e.correctedBy.length) h += ` <span class="chip warn">corrected</span>`;
    return h;
  }
  function card(e, terms) {
    const who = e.authors.map(name).join(", ");
    return `<article class="card"><div class="line1">${e.time ? `<span>${esc(e.time)}</span>` : ""}${chips(e)}</div>` +
      `<h2><a href="#/e/${enc(e.id)}">${highlight(e.title, terms)}</a></h2>` +
      `<div class="line1"><span>${esc(who)}${esc(withText(e.with))}</span>${(e.tags || []).map((t) => `<span class="chip">${esc(t)}</span>`).join(" ")}</div>` +
      `<p class="snip">${snippet(e, terms)}</p></article>`;
  }
  function cards(list, terms, limit) {
    if (!list.length) return `<p class="empty">No entries match.</p>`;
    let h = "", day = null;
    for (const e of list.slice(0, limit)) {
      if (e.date !== day) { day = e.date; h += `<h3 class="day">${esc(day)}</h3>`; }
      h += card(e, terms);
    }
    if (list.length > limit) h += `<p><button class="btn" data-more="${limit + 100}">Show ${Math.min(100, list.length - limit)} more of ${list.length - limit}</button></p>`;
    return h;
  }
  function openItems(list) {
    const out = [];
    for (const e of list) for (const [anchor, by] of Object.entries(e.resolved || {})) if (!by.length) {
      const b = (e.blocks || {})[anchor] || { name: "todo", text: "" };
      out.push({ e, anchor, name: b.name, text: b.text });
    }
    return out.sort((a, b) => a.e.date.localeCompare(b.e.date));
  }
  function table(head, rows, cls = "tbl") {
    return `<table class="${cls}"><thead><tr>${head.map((x) => `<th>${esc(x)}</th>`).join("")}</tr></thead><tbody>` +
      rows.map((r) => `<tr${r.cls ? ` class="${r.cls}"` : ""}>${r.cells.map((c) => `<td${typeof c === "number" ? ' class="num"' : ""}>${c && c.html != null ? c.html : esc(c)}</td>`).join("")}</tr>`).join("") +
      `</tbody></table>`;
  }

  // ------------------------------------------------------------------ views ---------------
  let limit = 100;
  function viewEntries() {
    const { list, Q } = filtered();
    const n = list.length;
    main.innerHTML = `<div class="summary"><button class="btn toggle-filters" data-act="filters">Filters</button>` +
      `<span>${n} of ${E.length} entries${anyFilter() ? " match" : ""}</span>` +
      `<label>Order <select id="sort"><option value="new">newest first</option><option value="old">oldest first</option>` +
      `<option value="relevance">best match</option></select></label>` +
      `<button class="btn" data-act="export">Export this selection</button></div>` + cards(list, Q.terms, limit);
    $("#sort").value = F.sort;
  }
  function viewOpen() {
    const { list, Q } = filtered();
    const items = openItems(list).filter((x) => !Q.terms.length || Q.terms.every((t) => norm(x.text + " " + x.e.title).includes(t)));
    main.innerHTML = `<div class="summary"><button class="btn toggle-filters" data-act="filters">Filters</button>` +
      `<span>${items.length} open item(s): issues and todos no later entry has resolved yet</span></div>` +
      (items.length ? table(["Open since", "", "Item", "Entry", "Project", "By"], items.map((x) => ({ cells: [
        { html: `${esc(x.e.date)}<br><span class="chip">${days(x.e.date, D.today)} d</span>` },
        { html: `<span class="chip ${x.name === "issue" ? "warn" : "open"}">${esc(x.name)}</span>` },
        { html: highlight(x.text, Q.terms) },
        { html: entryLink(x.e.id, x.anchor, x.e.title) },
        x.e.project + (x.e.subproject ? " · " + x.e.subproject : ""),
        x.e.authors.map(name).join(", ")] })), "tbl items") : `<p class="empty">Nothing open.</p>`);
  }
  function snapshotTable(s, other) {
    const ov = other ? Object.fromEntries(other.pvs.map((p) => [p.name, p])) : {};
    const rows = s.pvs.map((p) => {
      const o = ov[p.name];
      const changed = other && (!o || String(o.value) !== String(p.value));
      const cells = [p.name, typeof p.value === "number" ? p.value : String(p.value), p.unit || "", p.severity || ""];
      if (other) cells.push(o ? (typeof p.value === "number" && typeof o.value === "number" ? +(p.value - o.value).toPrecision(6) : String(o.value)) : "–");
      return { cells, cls: changed ? "changed" : "" };
    });
    return table(["PV", "Value", "Unit", "Severity"].concat(other ? ["Δ to other"] : []), rows);
  }
  function thread(e) {
    const seen = new Set([e.id]), todo = [e.id];
    while (todo.length) {
      const x = byId[todo.pop()];
      if (!x) continue;
      for (const y of [].concat(x.related, x.corrects ? [x.corrects] : [], x.correctedBy))
        if (y && !seen.has(y) && byId[y]) { seen.add(y); todo.push(y); }
    }
    return [...seen].map((i) => byId[i]).sort((a, b) => (a.date + a.id).localeCompare(b.date + b.id));
  }
  function viewEntry(id, anchor) {
    const e = byId[id];
    if (!e) { main.innerHTML = `<p class="empty">No entry ${esc(id)} in this view.</p>`; return; }
    const i = E.indexOf(e), prev = E[i - 1], next = E[i + 1], S = D.site;
    let h = `<div class="entry-head"><div class="crumbs"><a href="#/${toHash()}">← All entries</a>` +
      (prev ? `<a href="#/e/${enc(prev.id)}" title="${esc(prev.title)}">‹ earlier</a>` : "") +
      (next ? `<a href="#/e/${enc(next.id)}" title="${esc(next.title)}">later ›</a>` : "") + `</div>` +
      `<div class="meta">${chips(e)}</div><h1>${esc(e.title)}</h1>` +
      `<div class="meta"><span>${esc(e.date)}${e.time ? " " + esc(e.time) : ""}</span><span>·</span>` +
      `<span>${e.authors.map((a) => `<a href="#/person/${enc(a)}">${esc(name(a))}</a>`).join(", ")}${esc(withText(e.with))}</span><span>·</span>` +
      `<span title="When the entry was merged into the log book">${esc(fmtLogged(e.logged))}</span>` +
      (e.backfilled ? `<span>· backfilled ${esc(e.backfilled)}</span>` : "") +
      ((e.apparatus || []).length ? `<span>· on ${e.apparatus.map((a) => `<a href="#/apparatus/${enc(a)}">${esc(a)}</a>`).join(", ")}</span>` : "") +
      (e.release === "candidate" ? `<span class="chip">release candidate</span>` : "") +
      ((e.tags || []).map((t) => `<span class="chip">${esc(t)}</span>`).join(" ")) + `</div>`;
    h += `<div class="entry-actions">`;
    if (S) {
      h += e.pr ? `<a class="btn" href="${S.repo}/pull/${e.pr}">Discuss</a>` : `<a class="btn" href="${S.repo}/pulls?q=${enc(e.id)}">Discuss</a>`;
      h += `<a class="btn" href="${S.new_entry}&title=${enc("Correction: " + e.title)}&corrects=${enc(e.id)}&project=${enc(e.project)}">Correct this entry</a>`;
      h += `<a class="btn" href="${S.repo}/blob/${S.branch}/${e.path.split("/").map(enc).join("/")}">Source</a>`;
    }
    h += `<button class="btn" data-act="cite-id" data-id="${esc(e.id)}">Copy link to cite</button></div></div>`;
    for (const c of e.correctedBy) {
      const ce = byId[c];
      h += `<div class="banner red"><b>Corrected</b> by ${entryLink(c)}${ce ? ": " + esc((ce.text || "").slice(0, 260)) + (ce.text.length > 260 ? " …" : "") : ""}</div>`;
    }
    for (const r of e.redactedBy) h += `<div class="banner"><b>Redacted:</b> see ${entryLink(r)}.</div>`;
    if (e.corrects) h += `<div class="banner red"><b>Corrects</b> ${entryLink(e.corrects)}.</div>`;
    if (e.redacts) h += `<div class="banner"><b>Redacts</b> ${entryLink(e.redacts)}.</div>`;
    for (const r of e.resolves) {
      const [tid, a] = r.split("#"), t = byId[tid], b = t && (t.blocks || {})[a];
      h += `<div class="banner green"><b>Resolves</b> ${entryLink(tid, a)}${b ? ": " + esc(b.text) : ""}</div>`;
    }
    if ((e.parameters || []).length) h += table(["Parameter", "Value", "Unit", ""], e.parameters.map((p) => ({ cells: [p.name, typeof p.value === "number" ? p.value : String(p.value), p.unit || "", p.note || ""] })));
    if ((e.runs || []).length) h += `<p class="meta"><b>Runs:</b> ${e.runs.map(esc).join(", ")}</p>`;
    if ((e.attendees || []).length) h += `<p class="meta"><b>Attendees:</b> ${e.attendees.map((a) => esc(name(a))).join(", ")}</p>`;
    if (e.valid_until) h += `<p class="meta"><b>Valid until:</b> ${esc(e.valid_until)}${e.valid_until < D.today ? " (expired)" : ""}</p>`;
    h += `<div class="prose" id="body">${e.html}</div>`;
    e.epics.forEach((s, k) => {
      const others = E.filter((x) => x !== e).flatMap((x) => x.epics.filter((y) => y.group === s.group).map((y) => ({ x, y })));
      h += `<section class="more"><h2>EPICS snapshot · ${esc(s.group)}${s.label ? " · " + esc(s.label) : ""}</h2>` +
        (others.length ? `<label class="meta">Compare with <select data-snap="${k}"><option value="">—</option>${others.map((o, j) =>
          `<option value="${j}">${esc(o.x.date)} · ${esc(o.x.title)}${o.y.label ? " · " + esc(o.y.label) : ""}</option>`).join("")}</select></label>` : "") +
        `<div id="snap-${k}">${snapshotTable(s)}</div></section>`;
      e["_others" + k] = others;
    });
    const files = e.data.map((d) => ({ cells: [{ html: `<a href="${esc(d.url)}">${esc(d.file)}</a>` }, "data", d.source || ""] }))
      .concat(e.attachments.map((a) => ({ cells: [{ html: `<a href="${esc(a.url)}">${esc(a.file)}</a>` }, "attachment", a.description || ""] })));
    if (files.length) h += `<section class="more"><h2>Files</h2>${table(["File", "", "Source / note"], files)}</section>`;
    if (Object.keys(e.refs || {}).length) h += `<section class="more"><h2>References in the repository</h2><dl class="kv">${Object.entries(e.refs).map(([k, v]) => `<dt>${esc(k)}</dt><dd><code>${esc(v)}</code></dd>`).join("")}</dl></section>`;
    if (e.cites.length) h += `<section class="more"><h2>Cited</h2><ul class="links">${e.cites.map((k) => { const r = refBy[k]; return r ? `<li>${r.doi ? `<a href="${esc(r.doi)}">${esc(r.cite)}</a>` : esc(r.cite)}</li>` : `<li>${esc(k)}</li>`; }).join("")}</ul></section>`;
    const th = thread(e);
    if (th.length > 1) h += `<section class="more"><h2>Thread</h2><ul class="links thread">${th.map((x) => `<li class="${x === e ? "here" : ""}">${esc(x.date)} · ${x === e ? esc(x.title) : entryLink(x.id)}</li>`).join("")}</ul></section>`;
    if (e.backlinks.length) h += `<section class="more"><h2>Linked from</h2><ul class="links">${e.backlinks.map((b) => `<li>${esc((byId[b] || {}).date || "")} · ${entryLink(b)}</li>`).join("")}</ul></section>`;
    if (e.migrated_from) h += `<p class="meta">Migrated from ${esc(e.migrated_from)}.</p>`;
    main.innerHTML = h;
    // state of each issue / todo with an id
    for (const [a, by] of Object.entries(e.resolved || {})) {
      const el = document.getElementById("e-" + e.id + "--" + a);
      if (!el) continue;
      const s = document.createElement("span");
      s.className = "state " + (by.length ? "done" : "open");
      s.innerHTML = by.length ? "resolved in " + by.map((x) => entryLink(x)).join(", ") : "open";
      el.insertBefore(s, el.firstChild);
    }
    main.querySelectorAll("select[data-snap]").forEach((sel) => sel.addEventListener("change", () => {
      const k = +sel.dataset.snap, o = e["_others" + k][sel.value];
      $("#snap-" + k).innerHTML = snapshotTable(e.epics[k], o ? o.y : null);
    }));
    if (anchor) {
      const el = document.getElementById("e-" + e.id + "--" + anchor);
      if (el) { el.scrollIntoView({ block: "center" }); el.classList.add("flash"); }
    } else window.scrollTo(0, 0);
  }
  function wikiBlock(page) {
    const w = wikiBy[page];
    if (!w) return "";
    const S = D.site;
    const html = w.html.replace(/^\s*<h[1-6][^>]*>[\s\S]*?<\/h[1-6]>/, "");   // the page's own title is shown above it
    return `<div class="prose">${html}</div>` + (S ? `<p><a class="btn" href="${S.repo}/edit/${S.branch}/${S.wiki}/${page.split("/").map(enc).join("/")}.md">Edit this page</a></p>` : "");
  }
  function viewProjects() {
    const pc = count(projectsOf), open = openItems(E);
    main.innerHTML = `<h1 class="page-title">Projects</h1><div class="grid">` + D.projects.map((p) =>
      `<a class="tile" href="#/project/${enc(p.name)}"><b>${esc(p.name)}</b><span>${pc[p.name] || 0} entries · ${open.filter((x) => projectsOf(x.e).includes(p.name)).length} open</span></a>`).join("") + `</div>`;
  }
  function viewProject(n) {
    const p = D.projects.find((x) => x.name === n) || { name: n, subprojects: [] };
    const list = E.filter((e) => projectsOf(e).includes(n)).reverse();
    const open = openItems(list);
    main.innerHTML = `<div class="crumbs"><a href="#/projects">← Projects</a></div><h1 class="page-title">${esc(n)}</h1>` +
      (p.wiki ? wikiBlock(p.wiki) : `<p class="meta">No project page in the wiki yet.</p>`) +
      (p.subprojects.length ? `<p class="meta">Subprojects: ${p.subprojects.map((s) => `<a class="chip" href="#/?project=${enc(n)}&sub=${enc(n + "/" + s)}">${esc(s)}</a>`).join(" ")}</p>` : "") +
      `<section class="more"><h2>Open items (${open.length})</h2>${open.length ? `<ul class="links">${open.map((x) => `<li><span class="chip ${x.name === "issue" ? "warn" : "open"}">${esc(x.name)}</span> ${esc(x.text)} — ${entryLink(x.e.id, x.anchor, x.e.date)}</li>`).join("")}</ul>` : `<p class="meta">Nothing open.</p>`}</section>` +
      `<section class="more"><h2>Latest entries (${list.length}) · <a href="#/?project=${enc(n)}">all, with filters</a></h2>${cards(list, [], 15)}</section>`;
  }
  function viewApparatusList() {
    const ac = count((e) => e.apparatus || []);
    main.innerHTML = `<h1 class="page-title">Apparatus</h1>` + (D.apparatus.length ? `<div class="grid">` + D.apparatus.map((a) =>
      `<a class="tile" href="#/apparatus/${enc(a.id)}"><b>${esc(a.name)}</b><span>${ac[a.id] || 0} entries</span></a>`).join("") + `</div>` : `<p class="empty">No apparatus registered.</p>`);
  }
  function viewApparatus(id) {
    const a = D.apparatus.find((x) => x.id === id) || { id, name: id };
    const list = E.filter((e) => (e.apparatus || []).includes(id)).reverse();
    const current = list.filter((e) => ["calibration", "maintenance"].includes(e.kind) && (!e.valid_until || e.valid_until >= D.today));
    const incidents = list.filter((e) => e.kind === "incident");
    const snaps = list.filter((e) => e.epics.length);
    const li = (xs) => xs.length ? `<ul class="links">${xs.map((e) => `<li>${esc(e.date)} · ${entryLink(e.id)}${e.valid_until ? " (valid until " + esc(e.valid_until) + ")" : ""}</li>`).join("")}</ul>` : `<p class="meta">None.</p>`;
    main.innerHTML = `<div class="crumbs"><a href="#/apparatus">← Apparatus</a></div><h1 class="page-title">${esc(a.name)}</h1>` +
      (a.wiki ? wikiBlock(a.wiki) : "") +
      `<section class="more"><h2>Current calibrations and maintenance</h2>${li(current)}</section>` +
      `<section class="more"><h2>Incidents</h2>${li(incidents)}</section>` +
      `<section class="more"><h2>EPICS snapshots</h2>${li(snaps)}</section>` +
      `<section class="more"><h2>All entries (${list.length}) · <a href="#/?app=${enc(id)}">with filters</a></h2>${cards(list, [], 15)}</section>`;
  }
  function viewPeople() {
    const wc = count((e) => e.authors);
    main.innerHTML = `<h1 class="page-title">People</h1><div class="grid">` + Object.keys(wc).sort((a, b) => name(a).localeCompare(name(b))).map((w) =>
      `<a class="tile" href="#/person/${enc(w)}"><b>${esc(name(w))}</b><span>${wc[w]} entries</span></a>`).join("") + `</div>`;
  }
  function viewPerson(h) {
    const list = E.filter((e) => e.authors.includes(h)).reverse();
    main.innerHTML = `<div class="crumbs"><a href="#/people">← People</a></div><h1 class="page-title">${esc(name(h))}</h1>` +
      `<p class="meta">${list.length} entries · <a href="#/?who=${enc(h)}">with filters</a></p>` + cards(list, [], limit);
  }
  function viewWikiList() {
    const groups = {};
    for (const w of D.wiki) { const g = w.page.includes("/") ? w.page.split("/")[0] : ""; (groups[g] = groups[g] || []).push(w); }
    main.innerHTML = `<h1 class="page-title">Wiki</h1>` + (D.wiki.length ? Object.keys(groups).sort().map((g) =>
      `<section class="more"><h2>${esc(g || "pages")}</h2><ul class="links">${groups[g].map((w) => `<li><a href="#/wiki/${w.page.split("/").map(enc).join("/")}">${esc(w.title)}</a></li>`).join("")}</ul></section>`).join("") : `<p class="empty">The wiki is empty.</p>`);
  }
  function viewWiki(page) {
    const w = wikiBy[page];
    if (!w) { main.innerHTML = `<p class="empty">No wiki page ${esc(page)}.</p>`; return; }
    main.innerHTML = `<div class="crumbs"><a href="#/wiki">← Wiki</a></div><h1 class="page-title">${esc(w.title)}</h1>` + wikiBlock(page) +
      (w.backlinks.length ? `<section class="more"><h2>Linked from</h2><ul class="links">${w.backlinks.map((b) => `<li>${entryLink(b)}</li>`).join("")}</ul></section>` : "");
    window.scrollTo(0, 0);
  }
  function viewRefs() {
    const Q = parseQuery(F.q);
    const refs = D.references.filter((r) => Q.terms.every((t) => norm(r.cite + " " + r.key + " " + (r.html || "")).includes(t)));
    main.innerHTML = `<h1 class="page-title">References</h1><p class="meta">${refs.length} of ${D.references.length}. Cite in an entry as <code>[@Key]</code>.</p>` +
      refs.map((r) => `<div class="ref"><div><span class="short">${r.doi ? `<a href="${esc(r.doi)}">${esc(r.cite)}</a>` : esc(r.cite)}</span> <span class="chip">@${esc(r.key)}</span></div>` +
        `<div class="refline">${r.html || ""}</div>` + (r.citedBy.length ? `<div class="refline">Cited in ${r.citedBy.map((b) => entryLink(b)).join(" · ")}</div>` : "") + `</div>`).join("");
  }

  // ------------------------------------------------------------------ export dialog --------
  function exportDialog() {
    const { list } = filtered();
    const args = [];
    for (const p of F.project) args.push(`--project "${p}"`);
    for (const w of F.who) args.push(`--person ${w}`);
    for (const a of F.app) args.push(`--apparatus ${a}`);
    for (const k of F.kind) args.push(`--kind ${k}`);
    for (const t of F.tag) args.push(`--tag "${t}"`);
    if (F.from) args.push(`--from ${F.from}`);
    if (F.to) args.push(`--to ${F.to}`);
    if (F.q) args.push(`--query "${F.q.replace(/"/g, "'")}"`);
    const S = D.site;
    $("#dialog-body").innerHTML = `<h2>Export ${list.length} entries as a PDF</h2>` +
      `<p>An export for someone outside the lab is rendered with the lab notebook template and needs the PI's approval; every export is logged.</p>` +
      (S ? `<p><a class="btn primary" href="${S.export}">Request the export on GitHub</a> with these settings:</p>` : `<p>From a clone of the log book:</p>`) +
      `<pre>logbook export ${esc(args.join(" "))}</pre>`;
    $("#dialog").showModal();
  }

  // ------------------------------------------------------------------ routing --------------
  function route() {
    const raw = location.hash.slice(1) || "/";
    const at = raw.indexOf("?");
    const path = at < 0 ? raw : raw.slice(0, at), qs = at < 0 ? "" : raw.slice(at + 1);
    const parts = path.split("/").filter(Boolean).map(decodeURIComponent);
    const map = { e: "entry", open: "open", projects: "projects", project: "project", apparatus: parts[1] ? "app" : "apps",
                  people: "people", person: "person", wiki: parts[1] ? "wikipage" : "wiki", refs: "refs" };
    return { name: parts.length ? map[parts[0]] || "entries" : "entries", parts, qs };
  }
  const TABS = [["#/", "Entries", "entries", () => E.length], ["#/open", "Open items", "open", () => openItems(E).length],
    ["#/projects", "Projects", "projects"], ["#/apparatus", "Apparatus", "apps"], ["#/people", "People", "people"],
    ["#/wiki", "Wiki", "wiki", () => D.wiki.length], ["#/refs", "References", "refs", () => D.references.length]];
  function renderTabs(active) {
    const group = { entry: "entries", project: "projects", app: "apps", person: "people", wikipage: "wiki" }[active] || active;
    $("#tabs").innerHTML = TABS.filter((t) => t[2] !== "apps" || D.apparatus.length).map(([href, label, key, n]) =>
      `<a href="${href}" ${group === key ? 'aria-current="page"' : ""}>${label}${n ? `<span class="count">${n()}</span>` : ""}</a>`).join("");
  }
  function render() {
    const r = route();
    if (r.name === "entries" || r.name === "open") fromHash(r.qs);
    renderTabs(r.name);
    const withFilters = r.name === "entries" || r.name === "open";
    layout.classList.toggle("nofilters", !withFilters);
    filtersEl.classList.toggle("hidden", !withFilters);
    if (withFilters) renderFilters();
    ({ entries: viewEntries, open: viewOpen, entry: () => viewEntry(r.parts[1], r.parts[2]), projects: viewProjects,
       project: () => viewProject(r.parts.slice(1).join("/")), apps: viewApparatusList, app: () => viewApparatus(r.parts[1]),
       people: viewPeople, person: () => viewPerson(r.parts[1]), wiki: viewWikiList, wikipage: () => viewWiki(r.parts.slice(1).join("/")),
       refs: viewRefs })[r.name]();
  }

  // ------------------------------------------------------------------ wiring ---------------
  let timer;
  $("#q").addEventListener("input", (ev) => {
    clearTimeout(timer);
    timer = setTimeout(() => {
      F.q = ev.target.value.trim();
      limit = 100;
      const r = route().name;
      if (r === "refs") viewRefs(); else go(r === "open" ? "#/open" : "#/");
    }, 160);
  });
  document.addEventListener("keydown", (ev) => {
    if (ev.key === "/" && document.activeElement.tagName !== "INPUT" && document.activeElement.tagName !== "SELECT") { ev.preventDefault(); $("#q").focus(); }
    if (ev.key === "Escape" && document.activeElement === $("#q")) { $("#q").value = ""; $("#q").dispatchEvent(new Event("input")); }
  });
  main.addEventListener("click", (ev) => {
    const t = ev.target.closest("[data-act],[data-more]");
    if (!t) return;
    if (t.dataset.more) { limit = +t.dataset.more; render(); }
    else if (t.dataset.act === "export") exportDialog();
    else if (t.dataset.act === "filters") filtersEl.classList.toggle("open");
    else if (t.dataset.act === "cite-id") {
      const text = "[[" + t.dataset.id + "]]";
      try { navigator.clipboard.writeText(text); t.textContent = "Copied " + text; } catch (e) { t.textContent = text; }
    }
  });
  main.addEventListener("change", (ev) => { if (ev.target.id === "sort") { F.sort = ev.target.value; go("#/"); } });

  function theme(t) {
    if (t) document.documentElement.dataset.theme = t; else delete document.documentElement.dataset.theme;
    try { t ? localStorage.setItem("lb-theme", t) : localStorage.removeItem("lb-theme"); } catch (e) { /* private window */ }
  }
  try { const t = localStorage.getItem("lb-theme"); if (t) document.documentElement.dataset.theme = t; } catch (e) { /* none */ }
  const S = D.site;
  $("#actions").innerHTML = (S ? `<a class="btn primary" href="${S.new_entry}">New entry</a>` : "") +
    `<button class="btn" id="theme" title="Light, dark, or as the system">Theme</button>`;
  $("#theme").addEventListener("click", () => {
    const cur = document.documentElement.dataset.theme;
    theme(cur === undefined ? "dark" : cur === "dark" ? "light" : undefined);
  });
  $("#generated").textContent = `${E.length} entries · built ${D.generated.replace("T", " ")}`;
  window.addEventListener("hashchange", render);
  render();
})();
