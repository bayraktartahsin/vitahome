"""A very small PDF writer — enough for a clean, printable guide.

Written rather than pulled in because this machine has no PDF engine: macOS
dropped the HTML filter from cupsfilter, and pandoc has no LaTeX, weasyprint or
typst behind it. The alternative was shipping the guide as a wall of images,
which cannot be searched, selected or read aloud by a screen reader.

Only the PDF base-14 fonts are used (Helvetica, Helvetica-Bold, Courier), so
nothing has to be embedded and the file stays small. Text is measured with the
real font before it is wrapped, the same discipline the architecture diagram
uses, so a line never runs past the margin.
"""
from __future__ import annotations

import zlib
from pathlib import Path

from PIL import ImageFont

# Metrically equivalent to the PDF base-14 faces of the same names.
_FONT_FILES = {
    "H":  ("/System/Library/Fonts/Helvetica.ttc", 0),
    "HB": ("/System/Library/Fonts/Helvetica.ttc", 1),
    "C":  ("/System/Library/Fonts/Menlo.ttc", 0),
}
_PDF_FONT = {"H": "Helvetica", "HB": "Helvetica-Bold", "C": "Courier"}
_cache: dict = {}


def _font(name: str, size: int):
    key = (name, int(size))
    if key not in _cache:
        path, idx = _FONT_FILES[name]
        _cache[key] = ImageFont.truetype(path, int(size), index=idx)
    return _cache[key]


def width(text: str, font: str, size: float) -> float:
    """How wide this string will actually be drawn."""
    # Courier in the PDF is a fixed 600/1000 em; Menlo measures close but not
    # identically, so the monospace case is computed rather than measured.
    if font == "C":
        return len(text) * size * 0.6
    return _font(font, size).getlength(text) * (size / int(size))


def wrap(text: str, font: str, size: float, max_w: float) -> list[str]:
    """Greedy wrap on spaces. Long unbreakable tokens are left to overflow
    visibly rather than silently truncated — a clipped URL is worse than an
    ugly one."""
    out, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if line and width(trial, font, size) > max_w:
            out.append(line)
            line = word
        else:
            line = trial
    if line:
        out.append(line)
    return out or [""]


def _enc(s: str) -> bytes:
    """PDF strings in WinAnsi. Anything outside it becomes a plain equivalent,
    because a missing glyph in a printed guide is a support question."""
    subs = {
        "—": "-", "–": "-", "·": "-", "→": "->",
        "“": '"', "”": '"', "‘": "'", "’": "'",
        "…": "...", "▸": ">", "✓": "v", " ": " ",
    }
    for k, v in subs.items():
        s = s.replace(k, v)
    b = s.encode("cp1252", "replace")
    return b.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


class Pdf:
    """Accumulates pages of positioned text and coloured rectangles."""

    def __init__(self, w: float = 595.28, h: float = 841.89):   # A4 points
        self.w, self.h = w, h
        self.pages: list[list[bytes]] = []
        self.cur: list[bytes] = []

    def new_page(self) -> None:
        if self.cur:
            self.pages.append(self.cur)
        self.cur = []

    def rect(self, x, y, w, h, rgb) -> None:
        r, g, b = rgb
        self.cur.append(
            f"{r:.3f} {g:.3f} {b:.3f} rg {x:.2f} {self.h - y - h:.2f} "
            f"{w:.2f} {h:.2f} re f".encode())

    def text(self, x, y, s, font="H", size=11, rgb=(0, 0, 0)) -> None:
        r, g, b = rgb
        self.cur.append(
            b"BT " + f"{r:.3f} {g:.3f} {b:.3f} rg /{font} {size:.1f} Tf "
            f"{x:.2f} {self.h - y:.2f} Td ".encode()
            + b"(" + _enc(s) + b") Tj ET")

    def save(self, path: Path) -> None:
        if self.cur:
            self.pages.append(self.cur)

        objs: list[bytes] = []

        def add(b: bytes) -> int:
            objs.append(b)
            return len(objs)

        font_ids = {k: add(f"<< /Type /Font /Subtype /Type1 /BaseFont /{v} "
                           f"/Encoding /WinAnsiEncoding >>".encode())
                    for k, v in _PDF_FONT.items()}
        res = ("<< /Font << " +
               " ".join(f"/{k} {i} 0 R" for k, i in font_ids.items()) +
               " >> >>")

        # The Pages node is written after every page object, but each page has
        # to name it as its parent, so its id is reserved here. Three font
        # objects exist already and each page contributes two (its content
        # stream and the page itself); the node lands immediately after them.
        # Getting this off by one points every /Parent at the Catalog instead,
        # which most viewers silently tolerate and Acrobat rejects outright.
        pages_id = len(objs) + 2 * len(self.pages) + 1
        kids, page_ids = [], []
        for content in self.pages:
            stream = zlib.compress(b"\n".join(content))
            cid = add(b"<< /Length " + str(len(stream)).encode() +
                      b" /Filter /FlateDecode >>\nstream\n" + stream + b"\nendstream")
            pid = add(f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox "
                      f"[0 0 {self.w:.2f} {self.h:.2f}] /Resources {res} "
                      f"/Contents {cid} 0 R >>".encode())
            page_ids.append(pid)
            kids.append(f"{pid} 0 R")

        pid_pages = add(f"<< /Type /Pages /Count {len(page_ids)} "
                        f"/Kids [{' '.join(kids)}] >>".encode())
        root = add(f"<< /Type /Catalog /Pages {pid_pages} 0 R >>".encode())

        buf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = [0]
        for n, body in enumerate(objs, start=1):
            offsets.append(len(buf))
            buf += f"{n} 0 obj\n".encode() + body + b"\nendobj\n"
        xref = len(buf)
        buf += f"xref\n0 {len(objs) + 1}\n".encode()
        buf += b"0000000000 65535 f \n"
        for off in offsets[1:]:
            buf += f"{off:010d} 00000 n \n".encode()
        buf += (f"trailer\n<< /Size {len(objs) + 1} /Root {root} 0 R >>\n"
                f"startxref\n{xref}\n%%EOF\n").encode()
        _validate(bytes(buf), expect_pages=len(self.pages))
        path.write_bytes(bytes(buf))


def _validate(data: bytes, *, expect_pages: int) -> None:
    """Refuse to write a PDF that does not hold together.

    A malformed object graph is not visible in a preview — lenient viewers
    render it and Acrobat reports only a number. This checks the things that
    are cheap to check and expensive to discover later: every indirect
    reference resolves, every page points at the real Pages node, the page
    count is honest, and each xref offset lands on the object it claims.
    """
    import re

    ids = {int(m.group(1)) for m in re.finditer(rb"(?m)^(\d+) 0 obj", data)}
    refs = {int(m.group(1)) for m in re.finditer(rb"(\d+) 0 R", data)}
    missing = sorted(refs - ids)
    if missing:
        raise ValueError(f"PDF references objects that do not exist: {missing}")

    pages_m = re.search(rb"(\d+) 0 obj\n<< /Type /Pages", data)
    if not pages_m:
        raise ValueError("PDF has no /Pages node")
    pages_id = int(pages_m.group(1))

    parents = {int(m.group(1))
               for m in re.finditer(rb"/Type /Page /Parent (\d+) 0 R", data)}
    if parents != {pages_id}:
        raise ValueError(
            f"every page must have /Parent {pages_id} 0 R, found {sorted(parents)}")

    count = re.search(rb"/Type /Pages /Count (\d+)", data)
    if not count or int(count.group(1)) != expect_pages:
        raise ValueError(f"/Count disagrees with the {expect_pages} pages written")

    # each xref entry must point at the start of the object it indexes
    xref_at = int(re.search(rb"startxref\n(\d+)", data).group(1))
    entries = re.findall(rb"(\d{10}) 00000 n", data[xref_at:])
    for n, off in enumerate(entries, start=1):
        if not data[int(off):].startswith(f"{n} 0 obj".encode()):
            raise ValueError(f"xref entry {n} does not point at object {n}")
