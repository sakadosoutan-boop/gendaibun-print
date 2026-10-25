"""分量チェック — 新しい教材が原本の紙面に収まりそうかを、描画せずに見積もる。

Word のページ割りは実フォント（HG丸ゴシック・UD デジタル教科書体など）が無いと
再現できず、LibreOffice で数えたページ数は当てにならない（原本そのものでさえ
裏面の冒頭が 1 ページ目に食い込む）。そこで、縦書き 1 行に入る字数を
「段の長さ ÷ 文字の大きさ」で求め、教材の各行が何行分を占めるかを数えて、
原本と比べる。原本以下なら、紙面からはみ出すことはまずない。
"""

from __future__ import annotations

import math
from xml.etree import ElementTree as ET

from . import markup
from . import slots as slotlib
from .docxpkg import w

TWIP_MM = 25.4 / 1440
PT_MM = 25.4 / 72


def _section_of_paragraphs(root: ET.Element) -> dict[int, ET.Element]:
    """段落 → その段落が属するセクションの sectPr。"""
    body = root.find(w("body"))
    owner: dict[int, ET.Element] = {}
    pending: list[ET.Element] = []
    for child in body:
        if child.tag == w("p"):
            pending.append(child)
            ppr = child.find(w("pPr"))
            sect = ppr.find(w("sectPr")) if ppr is not None else None
            if sect is not None:
                for p in pending:
                    owner[id(p)] = sect
                pending = []
        elif child.tag == w("sectPr"):
            for p in pending:
                owner[id(p)] = child
    return owner


def _line_length_mm(sect: ET.Element) -> float:
    """縦書き 1 行の長さ（mm）。段組なら段の長さ。"""
    size, margin, cols = sect.find(w("pgSz")), sect.find(w("pgMar")), sect.find(w("cols"))
    height = int(size.get(w("h"))) - int(margin.get(w("top"))) - int(margin.get(w("bottom")))
    if sect.find(w("textDirection")) is None:     # 横書きなら幅で数える
        height = int(size.get(w("w"))) - int(margin.get(w("left"))) - int(margin.get(w("right")))
    num = int(cols.get(w("num"), "1")) if cols is not None else 1
    space = int(cols.get(w("space"), "0")) if cols is not None else 0
    return (height - space * (num - 1)) / num * TWIP_MM


def capacities(root: ET.Element, default_sz: int = 21) -> dict[str, int]:
    """スロット ID → そのスロットの段落の 1 行に入る字数。"""
    owner = _section_of_paragraphs(root)
    caps = {}
    for sid, (para, run) in slotlib.locate(root).items():
        sect = owner.get(id(para))
        if sect is None:            # 図形の中の文字などは数えない
            continue
        rpr = run.find(w("rPr"))
        sz = rpr.find(w("sz")) if rpr is not None else None
        points = int(sz.get(w("val")) if sz is not None else default_sz) / 2
        caps[sid] = max(1, int(_line_length_mm(sect) // (points * PT_MM)))
    return caps


def columns(text: str, cap: int) -> int:
    """1 段落が占める行数（縦書きの列数）。空行も 1 行と数える。"""
    return max(1, math.ceil(len(markup.plain(text)) / cap))


# ---------------------------------------------------------------- 横幅の見積もり（mm）
# 縦書きの 1 ページに並ぶ行の幅を足し上げる。行の幅＝字の大きさ×LINE_EM＋段落前の間隔。
#
# LINE_EM は『ぬくみ』原本から逆算した値。UD デジタル教科書体の字面の高さ（OS/2 の
# winAscent＋winDescent＝2369／2048＝1.157em）だけで数えると、原本の ① は 237mm、③（と
# ④ の前に入れていた空行 17 行）は 218mm にしかならない。どちらも Word では 1 ページちょうどに
# なっていたので、Word の行の高さは字面の約 1.2 倍（1.39em）。MEMO 帯の位置からの逆算も同じ。
PAGE_WIDTH_MM = (16838 - 720 * 2) * TWIP_MM      # A4 横の本文領域の幅
SAFETY_MM = 6.0                                   # 見積もりの誤差の分の余裕
FACE_EM = 2369 / 2048                             # 字面の高さ（いちばん狭く見積もったときの行の幅）
LINE_EM = FACE_EM * 1.2                           # Word の行の高さ（原本から逆算）


def line_mm(points: float, face_only: bool = False) -> float:
    """字の大きさ points の 1 行の幅（mm、段落前の間隔は含まない）。"""
    return points * PT_MM * (FACE_EM if face_only else LINE_EM)


def page_widths(root: ET.Element, default_sz: int = 21) -> list[float]:
    """ページ（「段落前で改ページ」で区切る）ごとの、行の幅の合計（mm）。"""
    body = root.find(w("body"))
    owner = _section_of_paragraphs(root)
    pages: list[float] = [0.0]
    for para in body:
        if para.tag != w("p"):
            continue
        ppr = para.find(w("pPr"))
        if ppr is not None and ppr.find(w("pageBreakBefore")) is not None and pages[-1]:
            pages.append(0.0)
        text = "".join(slotlib.run_text(r) for r in para.findall(w("r")) if slotlib.is_plain_text_run(r))
        sizes = []
        for run in para.findall(w("r")):
            rpr = run.find(w("rPr"))
            if slotlib.run_text(run) and rpr is not None and rpr.find(w("sz")) is not None:
                sizes.append(int(rpr.find(w("sz")).get(w("val"))))
        mark = ppr.find(w("rPr")) if ppr is not None else None
        if not sizes and mark is not None and mark.find(w("sz")) is not None:
            sizes.append(int(mark.find(w("sz")).get(w("val"))))
        points = max(sizes or [default_sz]) / 2
        sect = owner.get(id(para))
        length = _line_length_mm(sect) if sect is not None else 184.6
        cap = max(1, int(length // (points * PT_MM)))
        cols = max(1, math.ceil(len(text) / cap)) if text else 1
        before = 0.0
        if ppr is not None and ppr.find(w("spacing")) is not None:
            before = int(ppr.find(w("spacing")).get(w("before"), "0")) * TWIP_MM
        pages[-1] += cols * line_mm(points) + before
    return pages
