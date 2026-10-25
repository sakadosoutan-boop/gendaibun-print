"""図解・挿絵の差し込み。

教材データの区画の行に ``{"図": "figures/…/図1.svg", "行": 4, "幅": 23, "高さ": 130, "上": 25}``
と書くと、その場所に空行を「行」の数だけ取り、最初の空行に図を錨で留める。

* 図の XML は原本の画像（SVG と PNG の組。template/…/figure.xml）を写して、寸法と位置だけ変える
* 横位置は「段組基準」。縦書きでは錨の段落の行からの距離になるので、図は空けた行の帯の
  中央に来る。行数が増減して帯がずれても、図は帯について動く
* 縦位置は「段落基準」。縦書きでは段落の上端＝本文領域の上端
* 折り返しは「四角」。見積もりがずれても、文字は図をよけて流れる（重ならない）
* 解答の見せ方に合わせて、図の版（答えが赤字／_空欄／_黒）を選ぶ
* 入れるのは PNG だけ。原本の見本は SVG＋PNG の組だが、SVG の文字は描く側によって
  崩れる（LibreOffice では縦書きの文書の中で文字の並びが逆になった）ので、見本の
  SVG の参照（a:extLst）は外す。SVG は図を直すときの元として figures/ に置く
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

from . import volume
from .docxpkg import DocxPackage, w

WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
WP14 = "http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing"
IMAGE_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
EMU_MM = 36000
# 解答の見せ方 → 図の版
VARIANT = {"原本どおり": "", "答え": "", "空欄": "_空欄", "黒": "_黒"}


class FigureError(ValueError):
    pass


@dataclass
class Placement:
    label: str          # 「②・学習」など
    index: int          # 区画の何行目（0 始まり）に錨を置くか
    spec: dict          # 教材データの「図」の指定


def is_figure(item) -> bool:
    return isinstance(item, dict) and "図" in item


def _local(el: ET.Element) -> str:
    return el.tag.split("}")[-1]


def pitch_mm(para: ET.Element, face_only: bool = False) -> float:
    """縦書き 1 行の幅（mm）の見積もり（volume.line_mm＋段落前の間隔）。

    face_only=True は字面の高さだけで数えたいちばん狭い見積もり。図の幅はこれで
    空けた行に収まるようにしておけば、実際の行がもっと広くても図は帯からはみ出さない。
    """
    sz = 21
    for run in para.iter(w("r")):
        el = run.find(w("rPr"))
        if el is not None and el.find(w("sz")) is not None:
            sz = int(el.find(w("sz")).get(w("val")))
            break
    ppr = para.find(w("pPr"))
    before = 0
    if ppr is not None and ppr.find(w("spacing")) is not None:
        before = int(ppr.find(w("spacing")).get(w("before"), "0")) * 25.4 / 1440
    return volume.line_mm(sz / 2, face_only) + before


class Inserter:
    def __init__(self, package: DocxPackage, root: ET.Element, template_dir: Path, base_dir: Path, mode: str):
        sample = template_dir / "figure.xml"
        if not sample.exists():
            raise FigureError(f"図の見本がありません: {sample}（make_template で作り直してください）")
        self.sample = ET.fromstring(sample.read_text(encoding="utf-8"))
        self.package, self.root, self.base_dir = package, root, base_dir
        self.variant = VARIANT.get(mode, "")
        ids = [int(el.get("id")) for el in root.iter() if _local(el) == "docPr" and el.get("id", "").isdigit()]
        self.next_id = max(ids + [1000]) + 1
        self.count = 0          # 入れた画像ファイルの数
        self.placed = 0         # 入れた図の数
        self.warnings: list[str] = []

    def _media(self, data: bytes, ext: str) -> str:
        """画像をパッケージに入れ、関係 ID を返す。"""
        self.count += 1
        name = f"media/zukai{self.count}.{ext}"
        part = "word/" + name
        rels_name = "word/_rels/document.xml.rels"
        rels = self.package.parts[rels_name].decode("utf-8")
        used = {int(n) for n in re.findall(r'Id="rId(\d+)"', rels)}
        rid = f"rId{max(used | {0}) + 1}"
        rels = rels.replace("</Relationships>",
                            f'<Relationship Id="{rid}" Type="{IMAGE_REL}" Target="{name}"/></Relationships>')
        self.package.parts[rels_name] = rels.encode("utf-8")
        self.package.parts[part] = data
        self.package.names.append(part)
        types = self.package.parts["[Content_Types].xml"].decode("utf-8")
        if f'Extension="{ext}"' not in types:
            mime = {"png": "image/png"}[ext]
            types = types.replace("<Default ", f'<Default Extension="{ext}" ContentType="{mime}"/><Default ', 1)
            self.package.parts["[Content_Types].xml"] = types.encode("utf-8")
        return rid

    def place(self, para: ET.Element, spec: dict, label: str) -> None:
        svg = self.base_dir / spec["図"]
        stem = svg.with_suffix("")
        svg = stem.with_name(stem.name + self.variant + ".svg")
        png = svg.with_suffix(".png")
        for path in (svg, png):
            if not path.exists():
                raise FigureError(f"{label}: 図のファイルがありません: {path}"
                                  "（figures/…/make_figures.py で作ってください）")
        lines = int(spec.get("行", 1))
        width, height = float(spec["幅"]), float(spec["高さ"])
        top = float(spec.get("上", (184.6 - height) / 2))
        p = pitch_mm(para)
        band = lines * p
        narrow = lines * pitch_mm(para, face_only=True)
        if width > narrow + 0.5:
            self.warnings.append(f"{label}: 図の幅 {width:.0f}mm が、空けた {lines} 行の"
                                 f"いちばん狭い見積もり（{narrow:.0f}mm）より広い。行を増やすか図を細くする")
        if top + height > 184.6 - 4:
            self.warnings.append(f"{label}: 図の下端（{top + height:.0f}mm）が行の下端に近すぎる。"
                                 "空行が次の行へ押し出されるおそれがある")

        run = copy.deepcopy(self.sample)
        anchor = next(el for el in run.iter() if _local(el) == "anchor")
        anchor.set("behindDoc", "0")
        anchor.set("distL", "0")
        anchor.set("distR", "0")
        self.placed += 1
        anchor.set("relativeHeight", str(251700000 + self.placed))
        for key in (f"{{{WP14}}}anchorId", f"{{{WP14}}}editId"):
            anchor.attrib.pop(key, None)
        # 横: 空けた行の帯の中央（錨の行の右端から帯の幅だけ左へ）
        h_off = p - (band + width) / 2
        for el in anchor:
            if _local(el) == "positionH":
                el.set("relativeFrom", "column")
                el[0].text = str(round(h_off * EMU_MM))
            elif _local(el) == "positionV":
                el.set("relativeFrom", "paragraph")
                el[0].text = str(round(top * EMU_MM))
        cx, cy = str(round(width * EMU_MM)), str(round(height * EMU_MM))
        for el in run.iter():
            if _local(el) in ("extent", "ext") and el.get("cx") is not None:
                el.set("cx", cx)
                el.set("cy", cy)
        # 折り返し: なし → 四角（文字は図をよける）
        children = list(anchor)
        wrap = next(el for el in children if _local(el).startswith("wrap"))
        square = ET.Element(f"{{{WP}}}wrapSquare", {"wrapText": "bothSides"})
        anchor.insert(children.index(wrap), square)
        anchor.remove(wrap)
        title = spec.get("説明", stem.name)
        for el in run.iter():
            if _local(el) == "docPr":
                el.set("id", str(self.next_id))
                el.set("name", f"図解 {self.placed}")
                el.set("descr", title)
            elif _local(el) == "cNvPr":
                el.set("id", str(self.next_id))
                el.set("name", stem.name)
                el.set("descr", title)
        self.next_id += 1
        rid_png = self._media(png.read_bytes(), "png")
        for el in list(run.iter()):
            if _local(el) == "blip":
                el.set(f"{{{REL}}}embed", rid_png)
                for ext in [c for c in el if _local(c) == "extLst"]:
                    el.remove(ext)
        para.append(run)
