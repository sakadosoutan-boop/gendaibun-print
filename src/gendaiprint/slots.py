"""レイアウト（テンプレート）と文言（教材データ）を切り分ける層。

古文プリント（kobun-print）で確かめたやり方をそのまま使う。原本の組版は
A4 横・縦書きと、枠・MEMO 帯・アイコンなどのフローティング図形でできている。
これを作り直すと必ずどこかがずれるので、**原本の XML を組版の正本として残し、
文字の入る場所だけを「スロット」に置き換える**。

古文プリントと違うのは、スロットにする段落を文字の形から推し量らず、
レシピ（template/…/recipe.json）で段落番号を指定すること。現代文のプリントは
どの段落も同じ書体・同じ大きさで、見出しも本文もまぎれやすいため。

区画の段落は空行も含めて 1 段落 1 スロットにする。段落の中の素の文字 run を
1 つにまとめ、最初の文字の位置に目印 ⟦s0001⟧ を置く。行頭の空白だけの run と、
図形・アイコンを含む run はレイアウトとしてそのまま残す。
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from xml.etree import ElementTree as ET

from . import markup, rpr
from .docxpkg import XML_NS, w

SLOT_OPEN, SLOT_CLOSE = "⟦", "⟧"
SLOT_RE = re.compile(r"⟦([^⟧]+)⟧")

# run を丸ごとレイアウトとして残す子要素（局所名で判定する。mc:AlternateContent は
# w: の名前空間ではないので、w("AlternateContent") で探すと見落とす）
OPAQUE = {"drawing", "AlternateContent", "ruby", "fldChar", "instrText", "pict", "object"}
# 段落の中で文字の並びを分断するだけで意味を持たない要素
TRANSPARENT = {"proofErr", "bookmarkStart", "bookmarkEnd", "lastRenderedPageBreak"}


def local(el: ET.Element) -> str:
    return el.tag.split("}")[-1]


PLAIN = {"rPr", "t", "tab", "br", "lastRenderedPageBreak"}


def is_plain_text_run(el: ET.Element) -> bool:
    """文字だけの run か（書式＋文字・タブ・改行のみ）。"""
    return el.tag == w("r") and {local(c) for c in el} <= PLAIN


def run_text(run: ET.Element) -> str:
    out = []
    for c in run:
        name = local(c)
        if name == "t":
            out.append(c.text or "")
        elif name == "tab":
            out.append("\t")
        elif name == "br":
            out.append("\n")
    return "".join(out)


def has_layout(para: ET.Element) -> bool:
    """段落が図形の錨や改セクションを抱えているか（＝消したり複製したりできない）。"""
    for run in para.findall(w("r")):
        if {local(c) for c in run} & OPAQUE:
            return True
    ppr = para.find(w("pPr"))
    return ppr is not None and ppr.find(w("sectPr")) is not None


@dataclass
class Slot:
    slot_id: str
    text: str                                   # 短縮記法の文字列
    base: dict[str, str] = field(default_factory=dict)          # 基準の文字書式
    extra_spans: dict[str, dict] = field(default_factory=dict)  # 書式NN の定義
    local_spans: dict[str, dict] = field(default_factory=dict)  # このスロットだけの上書き


# ---------------------------------------------------------------- 抽出
def mark_paragraph(para: ET.Element, slot_id: str, registry: dict[str, str],
                   definitions: dict[str, dict], fallback: dict[str, str]) -> Slot:
    """段落の素の文字を 1 つのスロットにまとめ、目印を置く（para は書き換わる）。

    ``fallback`` は空行の段落に使う基準書式（段落記号の書式、無ければ区画の書式）。
    """
    for child in list(para):
        if local(child) == "proofErr":
            para.remove(child)
    runs = [c for c in para if is_plain_text_run(c)]
    # アイコンや図形のある段落では、行頭の空白だけの run は図形の前後の間合いなので
    # 残す。ほかの段落では行頭の空白は字下げ（＝文言）なのでスロットに含める。
    lead = []
    if has_layout(para):
        for run in runs:
            if run_text(run).strip():
                break
            lead.append(run)
        if len(lead) == len(runs):      # 空白だけの行は全部をスロットに
            lead = []
    group = [r for r in runs if r not in lead]

    if group:
        slot = _make_slot(slot_id, group, registry, definitions)
        position = list(para).index(group[0])
        for run in group:
            para.remove(run)
    else:
        mark = para.find(w("pPr"))
        mark = mark.find(w("rPr")) if mark is not None else None
        slot = Slot(slot_id, "", base=rpr.to_dict(mark) or dict(fallback))
        anchors = [i for i, c in enumerate(para) if local(c) != "pPr"]
        position = anchors[0] if anchors else len(para)
    para.insert(position, make_marker(slot.slot_id, slot.base))
    used = {p.span for p in markup.parse(slot.text)[0] if p.span}
    slot.extra_spans = {n: definitions[n] for n in sorted(used) if n in definitions}
    return slot


def _make_slot(slot_id, runs, registry, definitions) -> Slot:
    props = [rpr.to_dict(r.find(w("rPr"))) for r in runs]
    texts = [run_text(r) for r in runs]
    # 基準書式は「最も多くの文字を占める書式」。run の数で数えると、1 文字ずつに
    # 細切れになる括弧や記号のほうが多数派になってしまう。
    weight: Counter = Counter()
    for prop, text in zip(props, texts):
        weight[rpr.signature({"set": prop})] += len(text) or 0
    best = max(weight, key=lambda s: (weight[s], s))
    base = next(p for p in props if rpr.signature({"set": p}) == best)

    pieces: list[markup.Piece] = []
    local_spans: dict[str, dict] = {}
    for prop, text in zip(props, texts):
        if not text:
            continue
        delta = rpr.diff(base, prop)
        if not delta:
            span = None
        else:
            span = rpr.semantic_name(delta)
            if span is None:
                core = rpr.semantic_core(delta)
                if core is not None and local_spans.get(core, delta) == delta:
                    local_spans[core] = delta     # 意味の名前で呼び、書式は上書きで持つ
                    span = core
                else:
                    sig = rpr.signature(delta)
                    if sig not in registry:
                        registry[sig] = "書式%02d" % (len(registry) + 1)
                    span = registry[sig]
                    definitions[span] = delta
        if pieces and pieces[-1].span == span:
            pieces[-1].text += text
        else:
            pieces.append(markup.Piece(text, span))
    return Slot(slot_id, markup.render(pieces), base=base, local_spans=local_spans)


def make_marker(slot_id: str, base: dict[str, str]) -> ET.Element:
    run = ET.Element(w("r"))
    el = rpr.build(base)
    if el is not None:
        run.append(el)
    t = ET.SubElement(run, w("t"))
    t.set("{%s}space" % XML_NS, "preserve")
    t.text = f"{SLOT_OPEN}{slot_id}{SLOT_CLOSE}"
    return run


# ---------------------------------------------------------------- 目印の検索
def marker_of(run: ET.Element) -> str | None:
    if run.tag != w("r"):
        return None
    t = run.find(w("t"))
    if t is None or not t.text:
        return None
    m = SLOT_RE.fullmatch(t.text.strip())
    return m.group(1) if m else None


def locate(root: ET.Element) -> dict[str, tuple[ET.Element, ET.Element]]:
    """スロット ID → (段落, 目印の run)。"""
    found = {}
    for para in root.iter(w("p")):
        for run in para.findall(w("r")):
            sid = marker_of(run)
            if sid:
                found[sid] = (para, run)
    return found


# ---------------------------------------------------------------- 流し込み
def fill(
    root: ET.Element,
    values: dict[str, str],
    spans: dict[str, dict],
    local_spans: dict[str, dict[str, dict]] | None = None,
    recolour: dict[str, str] | None = None,
) -> list[str]:
    """目印を文言で置き換える。値の無い目印は消す（空欄にする）。

    ``recolour`` は「この色を別の色に読み替える」表。段落まるごと赤字で書かれた
    解答行は色が基準書式に乗っているので、ここで基準書式ごと塗り替える。
    戻り値は値が無かったスロット ID。
    """
    local_spans = local_spans or {}
    missing = []
    for sid, (para, run) in locate(root).items():
        if sid not in values:
            missing.append(sid)
            para.remove(run)
            continue
        base = rpr.recolour(rpr.to_dict(run.find(w("rPr"))), recolour)
        merged = {**spans, **local_spans.get(sid, {})}
        position = list(para).index(run)
        para.remove(run)
        for offset, new in enumerate(build_runs(values[sid], base, merged)):
            para.insert(position + offset, new)
    return missing


def build_runs(text: str, base: dict[str, str], spans: dict[str, dict]) -> list[ET.Element]:
    pieces, _ = markup.parse(text)
    runs = []
    for piece in pieces:
        delta = {} if piece.span is None else spans.get(piece.span) \
            or rpr.SEMANTIC_SPANS.get(piece.span) or rpr.LABEL_SPANS.get(piece.span)
        if delta is None:
            raise KeyError(f"書式表に無い書式名です: {piece.span}（{text!r}）")
        run = ET.Element(w("r"))
        el = rpr.build(rpr.apply(base, delta))
        if el is not None:
            run.append(el)
        for token in re.split(r"([\t\n])", piece.text):
            if token == "\t":
                ET.SubElement(run, w("tab"))
            elif token == "\n":
                ET.SubElement(run, w("br"))
            elif token:
                t = ET.SubElement(run, w("t"))
                t.set("{%s}space" % XML_NS, "preserve")
                t.text = token
        runs.append(run)
    return runs


def recolour_opaque(root: ET.Element, mapping: dict[str, str] | None) -> None:
    """図形の中など、スロットにならない run の文字色も読み替える。"""
    if not mapping:
        return
    for run in root.iter(w("r")):
        if not ({local(c) for c in run} & OPAQUE):
            continue
        for target in [run, *run.iter(w("r"))]:
            el = target.find(w("rPr"))
            colour = el.find(w("color")) if el is not None else None
            if colour is not None and colour.get(w("val")) in mapping:
                colour.set(w("val"), mapping[colour.get(w("val"))])
                colour.attrib.pop(w("themeColor"), None)
