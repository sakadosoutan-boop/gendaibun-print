"""図解・挿絵を SVG で描く道具（Python 標準ライブラリのみ）。

座標の単位は 0.1mm（幅 400 なら 40mm）。文字は UD デジタル教科書体で書くので、
Word で開いたときはプリントの本文と同じ書体になる。

答えの文字は ``ans()`` で赤字にする。``save()`` は 1 つの図から次の 3 つを書き出す
（src/build.py が --answers の指定に合わせて選ぶ）。

  名前.svg / 名前.png              答えは赤字（原本どおり・答え）
  名前_空欄.svg / 名前_空欄.png    答えは白字（空欄。配布用）
  名前_黒.svg / 名前_黒.png        答えは黒字

PNG は Word の古い版や LibreOffice のための代わりの画像で、LibreOffice（soffice）で描く。
"""

from __future__ import annotations

import math
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from xml.sax.saxutils import escape

FONT = "UD Digi Kyokasho NK-R, UD デジタル 教科書体 NK-R, IPAGothic, sans-serif"
RED = "#FF0000"
VARIANTS = {"": RED, "_空欄": "#FFFFFF", "_黒": "#000000"}
INK = "#000000"
GRAY = "#BFBFBF"
LIGHT = "#EDEDED"


class Figure:
    def __init__(self, width: float, height: float):
        self.w, self.h = width, height
        self.parts: list[str] = []

    # ------------------------------------------------------------ 基本の形
    def add(self, svg: str) -> None:
        self.parts.append(svg)

    def text(self, x, y, s, size=28, anchor="middle", bold=False, colour=INK, answer=False):
        """1 行の文字。y は文字の中心。answer=True なら答え（色が切り替わる）。"""
        fill = "{ANSWER}" if answer else colour
        weight = ' font-weight="bold"' if bold else ""
        self.add(f'<text x="{x:.1f}" y="{y + size * 0.36:.1f}" font-family="{FONT}" font-size="{size}"'
                 f' text-anchor="{anchor}" fill="{fill}"{weight}>{escape(s)}</text>')

    def lines(self, x, y, rows, size=28, gap=1.35, **kw):
        """複数行の文字。rows の要素は文字列か (文字列, True)＝答え。y は全体の中心。"""
        top = y - (len(rows) - 1) * size * gap / 2
        for k, row in enumerate(rows):
            s, answer = (row, False) if isinstance(row, str) else row
            self.text(x, top + k * size * gap, s, size=size, answer=answer, **kw)

    def ans(self, x, y, s, size=28, width=None, **kw):
        """答えの欄: 括弧〔 〕の中に答えを書く（配布用では括弧だけが残る）。"""
        width = width or size * (len(s) + 2.4)
        self.text(x - width / 2, y, "〔", size=size, anchor="start")
        self.text(x + width / 2, y, "〕", size=size, anchor="end")
        self.text(x, y, s, size=size, answer=True, **kw)

    def mixed(self, x, y, segments, size=28, bold=False):
        """地の文と答えを 1 行に並べる。segments は 文字列 か (答え, True) の並び。x は行の中心。"""
        widths = [size * len(seg) if isinstance(seg, str) else size * (len(seg[0]) + 2.4) for seg in segments]
        left = x - sum(widths) / 2
        for seg, w in zip(segments, widths):
            if isinstance(seg, str):
                self.text(left, y, seg, size=size, anchor="start", bold=bold)
            else:
                self.ans(left + w / 2, y, seg[0], size=size, width=w)
            left += w

    def box(self, x, y, w, h, r=12, fill="#FFFFFF", stroke=INK, width=3, dash=False):
        d = ' stroke-dasharray="10,7"' if dash else ""
        self.add(f'<rect x="{x - w / 2:.1f}" y="{y - h / 2:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{r}"'
                 f' fill="{fill}" stroke="{stroke}" stroke-width="{width}"{d}/>')

    def ellipse(self, x, y, rx, ry, fill="#FFFFFF", stroke=INK, width=3, dash=False):
        d = ' stroke-dasharray="10,7"' if dash else ""
        self.add(f'<ellipse cx="{x:.1f}" cy="{y:.1f}" rx="{rx:.1f}" ry="{ry:.1f}" fill="{fill}"'
                 f' stroke="{stroke}" stroke-width="{width}"{d}/>')

    def line(self, x1, y1, x2, y2, width=3, dash=False, colour=INK):
        d = ' stroke-dasharray="10,7"' if dash else ""
        self.add(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{colour}"'
                 f' stroke-width="{width}" stroke-linecap="round"{d}/>')

    def arrow(self, x1, y1, x2, y2, width=4, head=16, dash=False):
        """矢印（矢じりは塗りつぶしの三角。marker を使わないのでどの描画系でも同じに出る）。"""
        ang = math.atan2(y2 - y1, x2 - x1)
        bx, by = x2 - head * math.cos(ang), y2 - head * math.sin(ang)
        self.line(x1, y1, bx, by, width=width, dash=dash)
        px, py = -math.sin(ang) * head * 0.55, math.cos(ang) * head * 0.55
        self.add(f'<path d="M{x2:.1f},{y2:.1f} L{bx + px:.1f},{by + py:.1f} L{bx - px:.1f},{by - py:.1f} Z"'
                 f' fill="{INK}"/>')

    def path(self, d, fill="none", stroke=INK, width=3):
        self.add(f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{width}"'
                 f' stroke-linejoin="round" stroke-linecap="round"/>')

    # ------------------------------------------------------------ 挿絵（線画のピクトグラム）
    def person(self, x, y, s=1.0, pain=False, coat=False, sit=False):
        """人。(x, y) は頭の中心。s は大きさ（1.0 で高さ約 12mm）。"""
        r = 14 * s
        self.add(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="#FFFFFF" stroke="{INK}" stroke-width="3"/>')
        top = y + r + 4 * s
        body = (f"M{x - 20 * s:.1f},{top + 52 * s:.1f} L{x - 20 * s:.1f},{top + 12 * s:.1f} "
                f"Q{x - 20 * s:.1f},{top:.1f} {x - 8 * s:.1f},{top:.1f} L{x + 8 * s:.1f},{top:.1f} "
                f"Q{x + 20 * s:.1f},{top:.1f} {x + 20 * s:.1f},{top + 12 * s:.1f} L{x + 20 * s:.1f},{top + 52 * s:.1f} Z")
        self.path(body, fill=(LIGHT if not coat else "#FFFFFF"))
        legs = top + 52 * s
        if sit:
            self.path(f"M{x - 14 * s:.1f},{legs:.1f} L{x + 18 * s:.1f},{legs:.1f} L{x + 18 * s:.1f},{legs + 26 * s:.1f}")
            self.path(f"M{x - 2 * s:.1f},{legs:.1f} L{x + 26 * s:.1f},{legs + 2 * s:.1f} L{x + 26 * s:.1f},{legs + 26 * s:.1f}")
        else:
            self.line(x - 9 * s, legs, x - 9 * s, legs + 36 * s, width=4 * s + 1)
            self.line(x + 9 * s, legs, x + 9 * s, legs + 36 * s, width=4 * s + 1)
        if coat:      # 白衣と聴診器
            self.line(x, top, x - 9 * s, top + 22 * s)
            self.line(x, top, x + 9 * s, top + 22 * s)
            self.path(f"M{x - 7 * s:.1f},{top + 2 * s:.1f} Q{x - 14 * s:.1f},{top + 34 * s:.1f} {x:.1f},{top + 36 * s:.1f}"
                      f" Q{x + 14 * s:.1f},{top + 34 * s:.1f} {x + 7 * s:.1f},{top + 2 * s:.1f}", width=2)
            self.add(f'<circle cx="{x:.1f}" cy="{top + 38 * s:.1f}" r="{4 * s:.1f}" fill="{INK}"/>')
        if pain:      # おなかを押さえる手と、痛みのしるし
            self.path(f"M{x - 20 * s:.1f},{top + 14 * s:.1f} Q{x - 8 * s:.1f},{top + 36 * s:.1f} {x + 6 * s:.1f},{top + 32 * s:.1f}",
                      width=4 * s + 1)
            for k, (dx, dy) in enumerate(((28, 22), (30, 36), (24, 50))):
                zx, zy = x + dx * s, top + dy * s
                self.path(f"M{zx:.1f},{zy:.1f} l{6 * s:.1f},{-4 * s:.1f} l{2 * s:.1f},{6 * s:.1f} l{7 * s:.1f},{-5 * s:.1f}",
                          width=2.5)
            self.path(f"M{x - 6 * s:.1f},{y - 3 * s:.1f} l{4 * s:.1f},{2 * s:.1f} M{x + 6 * s:.1f},{y - 3 * s:.1f}"
                      f" l{-4 * s:.1f},{2 * s:.1f} M{x - 5 * s:.1f},{y + 7 * s:.1f} q{5 * s:.1f},{-4 * s:.1f} {10 * s:.1f},0",
                      width=2)

    def microscope(self, x, y, s=1.0):
        """顕微鏡。(x, y) は台の中心。"""
        self.box(x, y, 60 * s, 10 * s, r=3)                                    # 台
        self.path(f"M{x + 14 * s:.1f},{y - 5 * s:.1f} Q{x + 26 * s:.1f},{y - 40 * s:.1f} {x + 6 * s:.1f},{y - 66 * s:.1f}",
                  width=7 * s)                                                 # アーム
        self.box(x - 6 * s, y - 30 * s, 40 * s, 5 * s, r=2, fill=LIGHT)         # ステージ
        self.add(f'<rect x="{x - 12 * s:.1f}" y="{y - 82 * s:.1f}" width="{12 * s:.1f}" height="{40 * s:.1f}"'
                 f' rx="3" fill="#FFFFFF" stroke="{INK}" stroke-width="3"'
                 f' transform="rotate(-18 {x - 6 * s:.1f} {y - 62 * s:.1f})"/>')  # 鏡筒

    def germs(self, x, y, s=1.0):
        """病原菌（ばい菌の形）。"""
        for dx, dy, rot in ((0, 0, 20), (26, 10, -30), (8, 24, 70)):
            cx, cy = x + dx * s, y + dy * s
            self.add(f'<ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{11 * s:.1f}" ry="{6 * s:.1f}" fill="{GRAY}"'
                     f' stroke="{INK}" stroke-width="2" transform="rotate({rot} {cx:.1f} {cy:.1f})"/>')
            for k in range(6):
                a = math.radians(rot + k * 60)
                self.line(cx + 10 * s * math.cos(a), cy + 10 * s * math.sin(a),
                          cx + 15 * s * math.cos(a), cy + 15 * s * math.sin(a), width=1.5)

    def cloud(self, x, y, s=1.0, bolt=True):
        """雷雲（神の怒り）。"""
        self.path(f"M{x - 34 * s:.1f},{y + 8 * s:.1f} a{12 * s:.1f},{12 * s:.1f} 0 0 1 {8 * s:.1f},{-22 * s:.1f}"
                  f" a{16 * s:.1f},{16 * s:.1f} 0 0 1 {28 * s:.1f},{-8 * s:.1f} a{14 * s:.1f},{14 * s:.1f} 0 0 1 {24 * s:.1f},{8 * s:.1f}"
                  f" a{11 * s:.1f},{11 * s:.1f} 0 0 1 {8 * s:.1f},{22 * s:.1f} Z", fill=LIGHT)
        if bolt:
            self.path(f"M{x - 2 * s:.1f},{y + 8 * s:.1f} l{-10 * s:.1f},{18 * s:.1f} l{10 * s:.1f},0 l{-8 * s:.1f},{18 * s:.1f}"
                      f" l{20 * s:.1f},{-24 * s:.1f} l{-10 * s:.1f},0 l{8 * s:.1f},{-12 * s:.1f} Z", fill=INK, width=1.5)

    def monitor(self, x, y, w, h, rows, size=22):
        """検査結果の画面（数値の並び）。"""
        self.box(x, y, w, h, r=6, fill="#FFFFFF", width=3)
        self.box(x, y + h / 2 + 6, w * 0.3, 8, r=2, fill=INK, width=1)
        self.lines(x, y, rows, size=size, gap=1.3)

    def scale(self, x, y, s=1.0, tilt=0.0):
        """天秤。(x, y) は支点。tilt は右側が下がる量（0.1mm）。"""
        self.path(f"M{x:.1f},{y:.1f} L{x - 12 * s:.1f},{y + 70 * s:.1f} L{x + 12 * s:.1f},{y + 70 * s:.1f} Z", fill=LIGHT)
        lx, ly, rx, ry = x - 70 * s, y - tilt, x + 70 * s, y + tilt
        self.line(lx, ly, rx, ry, width=5)
        for px, py in ((lx, ly), (rx, ry)):
            self.line(px, py, px - 22 * s, py + 34 * s, width=2)
            self.line(px, py, px + 22 * s, py + 34 * s, width=2)
            self.path(f"M{px - 26 * s:.1f},{py + 34 * s:.1f} Q{px:.1f},{py + 48 * s:.1f} {px + 26 * s:.1f},{py + 34 * s:.1f} Z",
                      fill=LIGHT)

    def dna(self, x, y, h, s=1.0):
        """遺伝子（二重らせん）。(x, y) は上端の中心。"""
        a, b, steps = [], [], 24
        for k in range(steps + 1):
            t = k / steps
            yy = y + h * t
            a.append((x + 14 * s * math.sin(t * 4 * math.pi), yy))
            b.append((x - 14 * s * math.sin(t * 4 * math.pi), yy))
            if k % 2 == 0:
                self.line(a[-1][0], yy, b[-1][0], yy, width=1.5)
        for pts in (a, b):
            self.path("M" + " L".join(f"{px:.1f},{py:.1f}" for px, py in pts), width=3)

    def sprout(self, x, y, s=1.0):
        """双葉（自然）。(x, y) は根もと。"""
        self.line(x, y, x, y - 36 * s, width=3)
        self.path(f"M{x:.1f},{y - 30 * s:.1f} Q{x - 30 * s:.1f},{y - 50 * s:.1f} {x - 34 * s:.1f},{y - 30 * s:.1f}"
                  f" Q{x - 16 * s:.1f},{y - 18 * s:.1f} {x:.1f},{y - 30 * s:.1f} Z", fill=LIGHT)
        self.path(f"M{x:.1f},{y - 30 * s:.1f} Q{x + 30 * s:.1f},{y - 50 * s:.1f} {x + 34 * s:.1f},{y - 30 * s:.1f}"
                  f" Q{x + 16 * s:.1f},{y - 18 * s:.1f} {x:.1f},{y - 30 * s:.1f} Z", fill=LIGHT)
        self.path(f"M{x - 30 * s:.1f},{y:.1f} Q{x:.1f},{y - 8 * s:.1f} {x + 30 * s:.1f},{y:.1f}", width=3)

    def scissors(self, x, y, s=1.0):
        """はさみ（切り離し）。"""
        for dy in (-7, 7):
            self.add(f'<circle cx="{x - 16 * s:.1f}" cy="{y + dy * s:.1f}" r="{6 * s:.1f}" fill="#FFFFFF"'
                     f' stroke="{INK}" stroke-width="2.5"/>')
        self.line(x - 11 * s, y - 4 * s, x + 18 * s, y + 6 * s, width=3)
        self.line(x - 11 * s, y + 4 * s, x + 18 * s, y - 6 * s, width=3)

    def balloon(self, x, y, w, h, s, tail=(0, 1), size=26):
        """吹き出し。tail は尾の向き（-1〜1, -1〜1）。"""
        tx, ty = tail
        self.box(x, y, w, h, r=h / 2, width=2.5)
        bx, by = x + tx * w * 0.25, y + ty * h / 2
        self.path(f"M{bx - 6:.1f},{by:.1f} L{bx + tx * 14:.1f},{by + ty * 16:.1f} L{bx + 6:.1f},{by:.1f}",
                  fill="#FFFFFF", width=2.5)
        self.add(f'<rect x="{bx - 7:.1f}" y="{by - (3 if ty > 0 else -1):.1f}" width="14" height="3" fill="#FFFFFF"/>')
        self.text(x, y, s, size=size)

    # ------------------------------------------------------------ 書き出し
    def svg(self, answer_colour: str) -> str:
        body = "\n".join(self.parts).replace("{ANSWER}", answer_colour)
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w / 10:.1f}mm" height="{self.h / 10:.1f}mm"'
                f' viewBox="0 0 {self.w:.0f} {self.h:.0f}">\n<rect width="100%" height="100%" fill="#FFFFFF"/>\n'
                f"{body}\n</svg>\n")

    def save(self, stem: Path, png: bool = True) -> list[Path]:
        stem.parent.mkdir(parents=True, exist_ok=True)
        written = []
        for suffix, colour in VARIANTS.items():
            path = stem.with_name(stem.name + suffix + ".svg")
            path.write_text(self.svg(colour), encoding="utf-8")
            written.append(path)
            if png:
                written.append(to_png(path, self.svg(colour)))
        return written


def to_png(svg_path: Path, svg_text: str, scale: int = 4) -> Path:
    """LibreOffice で PNG にする（約 380dpi。SVG を 4 倍の寸法にして描かせる）。"""
    if not shutil.which("soffice"):
        raise RuntimeError("PNG を作るには LibreOffice（soffice）が要ります")
    big = re.sub(r'width="([\d.]+)mm" height="([\d.]+)mm"',
                 lambda m: f'width="{float(m.group(1)) * scale:.1f}mm" height="{float(m.group(2)) * scale:.1f}mm"',
                 svg_text, count=1)
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / (svg_path.stem + ".svg")
        src.write_text(big, encoding="utf-8")
        subprocess.run(["soffice", "--headless", "--convert-to", "png", "--outdir", tmp, str(src)],
                       check=True, capture_output=True)
        out = svg_path.with_suffix(".png")
        shutil.copyfile(Path(tmp) / (svg_path.stem + ".png"), out)
    return out
