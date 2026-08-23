#!/usr/bin/env python3
"""Generate PDF from docs/USER_MANUAL.md (requires fpdf2)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from fpdf import FPDF

ROOT = Path(__file__).resolve().parents[1]
MD_PATH = ROOT / "docs" / "USER_MANUAL.md"
PDF_PATH = ROOT / "docs" / "USER_MANUAL.pdf"

# Windows Arial supports Cyrillic; fallback for Linux/macOS below.
FONT_CANDIDATES = [
    Path(r"C:\Windows\Fonts\arial.ttf"),
    Path(r"C:\Windows\Fonts\arialbd.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/TTF/DejaVuSans.ttf"),
    Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
]


def find_font() -> tuple[Path, Path | None]:
    regular = None
    bold = None
    for path in FONT_CANDIDATES:
        if path.exists():
            name = path.name.lower()
            if "bd" in name or "bold" in name:
                bold = bold or path
            else:
                regular = regular or path
    if regular is None:
        raise FileNotFoundError(
            "No Unicode TTF font found. Install DejaVu Sans or run on Windows."
        )
    return regular, bold


class ManualPDF(FPDF):
    def __init__(self) -> None:
        super().__init__(format="A4")
        self.set_margins(15, 15, 15)
        self.set_auto_page_break(auto=True, margin=18)
        regular, bold = find_font()
        self.add_font("Body", "", str(regular))
        if bold:
            self.add_font("Body", "B", str(bold))
        else:
            self.add_font("Body", "B", str(regular))
        self._body_size = 11
        self._h1_size = 16
        self._h2_size = 13
        self._h3_size = 12

    def header(self) -> None:
        if self.page_no() == 1:
            return
        self.set_font("Body", size=9)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, "Тихие объятия — пользовательская инструкция", align="C")
        self.ln(4)
        self.set_text_color(0, 0, 0)

    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("Body", size=9)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, f"Стр. {self.page_no()}", align="C")
        self.set_text_color(0, 0, 0)

    def _write_block(self, h: float, text: str) -> None:
        """multi_cell leaves x at the line end; reset before the next block."""
        self.set_x(self.l_margin)
        self.multi_cell(0, h, text)
        self.set_x(self.l_margin)

    def write_md_line(self, line: str) -> None:
        line = line.rstrip()
        if not line.strip():
            self.ln(4)
            return

        if line.startswith("# "):
            self.ln(6)
            self.set_font("Body", "B", self._h1_size)
            self._write_block(8, strip_md(line[2:]))
            self.ln(2)
            return

        if line.startswith("## "):
            self.ln(5)
            self.set_font("Body", "B", self._h2_size)
            self._write_block(7, strip_md(line[3:]))
            self.ln(2)
            return

        if line.startswith("### "):
            self.ln(4)
            self.set_font("Body", "B", self._h3_size)
            self._write_block(6, strip_md(line[4:]))
            self.ln(1)
            return

        if line.strip() == "---":
            self.ln(2)
            self.set_draw_color(200, 200, 200)
            y = self.get_y()
            self.line(self.l_margin, y, self.w - self.r_margin, y)
            self.ln(4)
            return

        if line.startswith("| ") and line.endswith("|"):
            if re.match(r"^\|\s*[-:| ]+\|\s*$", line.strip()):
                return
            self.set_font("Body", size=self._body_size - 1)
            self._write_block(5, strip_md(line.replace("|", "  ").strip()))
            return

        if line.startswith("- ") or line.startswith("* "):
            self.set_font("Body", size=self._body_size)
            self._write_block(6, "  • " + render_inline(strip_md(line[2:])))
            return

        if re.match(r"^\d+\.\s", line):
            self.set_font("Body", size=self._body_size)
            self._write_block(6, "  " + render_inline(strip_md(line)))
            return

        if line.startswith("> "):
            self.set_font("Body", size=self._body_size)
            self.set_text_color(60, 60, 60)
            self._write_block(6, render_inline(strip_md(line[2:])))
            self.set_text_color(0, 0, 0)
            return

        self.set_font("Body", size=self._body_size)
        self._write_block(6, render_inline(strip_md(line)))

    def write_code_block_line(self, line: str) -> None:
        self.set_font("Body", size=self._body_size - 1)
        self.set_text_color(40, 40, 40)
        self._write_block(5, strip_md(line))
        self.set_text_color(0, 0, 0)


def strip_md(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    # fpdf2 + Arial may fail on emoji; strip for readable PDF text.
    text = text.replace("➡️", "->").replace("◀️", "<-")
    text = text.replace("✅", "[v]").replace("❌", "[x]").replace("⚠️", "[!]")
    text = text.replace("2️⃣", "2.").replace("3️⃣", "3.")
    text = re.sub(r"[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0000FE0F]", "", text)
    return text.strip()


def render_inline(text: str) -> str:
    return strip_md(text)


def build_pdf(md_text: str, output: Path) -> None:
    pdf = ManualPDF()
    pdf.add_page()
    pdf.set_font("Body", size=11)

    in_code = False
    for raw_line in md_text.splitlines():
        line = raw_line.rstrip("\n")
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            pdf.write_code_block_line(line)
            continue
        pdf.write_md_line(line)

    output.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(output))


def main() -> int:
    if not MD_PATH.exists():
        print(f"Missing {MD_PATH}", file=sys.stderr)
        return 1
    build_pdf(MD_PATH.read_text(encoding="utf-8"), PDF_PATH)
    print(f"Generated {PDF_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
