// The information strip that `matplotlib/labfig.py` saves below a figure (who made it, when,
// with which template, where it lives) is for the file, not for the document: the themes cut
// it off. A catalog entry says how tall its strip is (`info_strip: 0.4`, inches at the file's
// natural size); entries without it are shown whole, as before.

/// The image at `path` without its bottom `strip` (a length at the file's natural size), as
/// large as fits in `width` x `height` (each a length, ratio, relative length, or auto),
/// keeping its aspect ratio.
#let strip-image(path, strip: 0pt, alt: none, width: auto, height: auto) = layout(size => {
  let nat = measure(image(path))
  let (vw, vh) = (nat.width, nat.height - strip)
  let resolve(v, full) = if v == auto { none } else if type(v) == ratio { full * v } else if type(v) == relative { v.length + full * v.ratio } else { v }
  let w = resolve(width, size.width)
  let h = resolve(height, size.height)
  let k = if w != none and h != none { calc.min(w / vw, h / vh) } else if w != none { w / vw } else if h != none { h / vh } else { 1.0 }
  // The image gets its full height explicitly: given only a width, Typst limits it to the clip
  // box's height and crops it centred ("cover"), cutting top and bottom instead of the strip.
  box(width: vw * k, height: vh * k, clip: true,
    place(top + left, image(path, width: nat.width * k, height: nat.height * k, fit: "stretch", alt: alt)))
})

/// The strip height of a catalog entry, as a length (0pt when the entry has none).
#let entry-strip(e) = e.at("info_strip", default: 0) * 1in
