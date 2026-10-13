-- After citeproc: turns the log book's Markdown into Typst (the PDF) or HTML (the view).
-- Python prepares the input (lablogbook/render.py): each entry is a Div .lb-entry, each wiki page
-- a Div .lb-wiki, each figure a Div .lb-fig with a key; [[links]] are links to logbook:...
-- Data from Python, in the JSON file named by $LB_DATA (not pandoc metadata, which would be read
-- as Markdown): doi (citation key -> DOI url), fig (key -> figure fields), wiki_in (pages present).

local typst = FORMAT:match("typst") ~= nil
local meta_doi, meta_fig, wiki_in = {}, {}, {}

local CALLOUT = {decision = true, finding = true, issue = true, todo = true, context = true, incident = true}
local TYPST_FN = {decision = "decision", finding = "finding", issue = "issue", todo = "todo",
                  context = "context-box", incident = "incident"}
local HTML_LABEL = {decision = "Decision", finding = "Finding", issue = "Issue → cause → fix",
                    todo = "Open item", context = "Background", incident = "Incident"}

local function str(v) return v and pandoc.utils.stringify(v) or nil end

local function shift_headers(blocks, by)
  return pandoc.Blocks(blocks):walk({Header = function(h) h.level = math.min(h.level + by, 6); return h end})
end

local function esc(s)
  return (s:gsub("&", "&amp;"):gsub("<", "&lt;"):gsub(">", "&gt;"):gsub('"', "&quot;"))
end

local function tstr(s)   -- a Typst string literal
  return '"' .. s:gsub("\\", "\\\\"):gsub('"', '\\"') .. '"'
end

local function figure(key)
  local f = meta_fig[key]
  if not f then
    return pandoc.Para({pandoc.Str("[missing figure " .. key .. "]")})
  end
  if typst then
    local cap = f.caption_typst or tstr(f.caption)
    return pandoc.RawBlock("typst", string.format(
      "#figure(strip-image(%s, strip: %sin, alt: %s, width: %s), caption: [#%s])%s",
      tstr(f.typst_path), f.strip_in, tstr(f.alt), f.width or "62%", cap,
      f.label and (" <" .. f.label .. ">") or ""))
  end
  -- the figure (its SVG), with the labfig strip cropped; a click opens it on its own
  return pandoc.RawBlock("html", string.format(
    '<figure class="lb-fig"%s><a class="lb-crop" href="@@FIGVEC:%s@@" target="_blank" rel="noopener" ' ..
    'title="Open the vector original" style="aspect-ratio: %s / %s">' ..
    '<img src="@@FIG:%s@@" data-png="@@FIGPNG:%s@@" alt="%s" loading="lazy"></a>' ..
    '<figcaption>%s</figcaption></figure>',
    f.label and (' id="' .. f.label .. '"') or "", esc(key), f.w, f.h_visible, esc(key), esc(key), esc(f.alt), esc(f.caption)))
end

local inner   -- callouts and figures inside an entry (defined below)

local function Div(el)
  if el.classes:includes("lb-entry") or el.classes:includes("lb-wiki") then
    local id = el.attributes["data-id"]
    local kind = el.classes:includes("lb-entry") and "ENTRY" or "WIKI"
    local by = kind == "ENTRY" and 2 or 1
    -- pandoc does not run this filter again on what a handler returns, so convert the
    -- blocks inside the entry here (bottom-up, so nested blocks are handled first)
    local content = shift_headers(el.content, by):walk({Div = inner})
    local marker = typst and pandoc.RawBlock("typst", "// @@" .. kind .. " " .. id)
                          or pandoc.RawBlock("html", "<!--@@" .. kind .. " " .. id .. "-->")
    local out = pandoc.Blocks({marker})
    out:extend(content)
    return out
  end
  return inner(el)
end

inner = function(el)
  if el.classes:includes("lb-fig") then
    return figure(el.attributes["key"])
  end
  for name, _ in pairs(CALLOUT) do
    if el.classes:includes(name) then
      if typst then
        local out = pandoc.Blocks({pandoc.RawBlock("typst", "#" .. TYPST_FN[name] .. "[")})
        out:extend(el.content)
        local close = "]"
        if el.identifier ~= "" then close = close .. " <e-" .. el.identifier .. ">" end
        out:insert(pandoc.RawBlock("typst", close))
        return out
      end
      local id = el.identifier ~= "" and (' id="e-' .. el.identifier .. '"') or ""
      local out = pandoc.Blocks({pandoc.RawBlock("html", '<div class="callout ' .. name .. '"' .. id ..
        '><div class="callout-label">' .. HTML_LABEL[name] .. '</div>')})
      out:extend(el.content)
      out:insert(pandoc.RawBlock("html", "</div>"))
      return out
    end
  end
end

local function Link(el)
  local t = el.target
  if t:sub(1, 8) == "logbook:" then
    local rest = t:sub(9)
    local what, target = rest:match("^(%a+)/(.+)$")
    if what == "entry" then
      local id, anchor = target:match("^([^#]+)#?(.*)$")
      local lab = "e-" .. id .. (anchor ~= "" and ("--" .. anchor) or "")
      if typst then
        local out = pandoc.Inlines({pandoc.RawInline("typst", "#link(<" .. lab .. ">)[")})
        out:extend(el.content)
        out:insert(pandoc.RawInline("typst", "]"))
        return out
      end
      el.target = "#/e/" .. id .. (anchor ~= "" and ("/" .. anchor) or "")
      el.classes:insert("lb-link")
      return el
    elseif what == "wiki" then
      if typst then
        if wiki_in[target] then
          local out = pandoc.Inlines({pandoc.RawInline("typst", "#link(<w-" .. target:gsub("/", "-") .. ">)[")})
          out:extend(el.content)
          out:insert(pandoc.RawInline("typst", "]"))
          return out
        end
        return pandoc.Emph(el.content)
      end
      el.target = "#/wiki/" .. target
      el.classes:insert("lb-link")
      return el
    end
  end
end

local function Cite(el)
  local key = el.citations[1] and el.citations[1].id
  local url = key and meta_doi[key]
  if not url then return nil end
  return pandoc.Link(el.content, url, "", pandoc.Attr("", {"lb-cite"}))
end

do
  local path = os.getenv("LB_DATA")
  if path then
    local fh = io.open(path, "r")
    if fh then
      local data = pandoc.json.decode(fh:read("a"), false)
      fh:close()
      meta_doi = data.doi or {}
      meta_fig = data.fig or {}
      for _, w in ipairs(data.wiki_in or {}) do wiki_in[w] = true end
    end
  end
end

return {
  {Div = Div, Link = Link, Cite = Cite, traverse = "topdown"},
}
