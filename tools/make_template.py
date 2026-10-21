#!/usr/bin/env python3
"""益田先生の現代文プリント（docx）から、授業プリントのテンプレートを作る。

    python3 tools/make_template.py 原本.docx --name 授業プリント

template/<名前>/recipe.json（手順）に従って原本を加工し、次のものを作る。

  template/<名前>/base.docx      組版の正本。区画の段落に ⟦s0001⟧ の目印がある
  template/<名前>/spans.json     書式表（原本に残る細かな書式の差）
  template/<名前>/regions.json   区画表（①〜④ の「ヘッダ」「学習」「脚問」…）
  template/<名前>/defaults.json  元のプリントの文言（スロットごと）
  data/_雛形_<名前>.json          空の雛形

  --stripped PATH   目印を置く直前の docx（原本にレシピを当てただけのもの）も書き出す。
                    tests/verify.py が「テンプレート＋原本の文言」と 1 ドット比べる相手。
  --data PATH       元のプリントの中身を教材形式で書き出す（原本の再現用）。

原本の組版（段落・図形・セクション）はレシピで指定したものだけを変え、ほかは
原本の XML のまま残す。OOXML を自前で組み立てて置き換えることはしない。
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gendaiprint import markup, rpr  # noqa: E402
from gendaiprint import slots as slotlib  # noqa: E402
from gendaiprint.docxpkg import DocxPackage, w  # noqa: E402

REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
WP_NS = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"

# pPr の子要素の並び（スキーマ順）。pageBreakBefore を差し込む位置を決めるのに使う。
_BEFORE_PAGE_BREAK = {"pStyle", "keepNext", "keepLines"}


class RecipeError(ValueError):
    pass


def _dump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _text(el: ET.Element) -> str:
    return "".join(t.text or "" for t in el.iter(w("t")))


def _runs_with_docpr(root: ET.Element) -> dict[int, tuple[ET.Element, ET.Element]]:
    """docPr の id → (その図形を抱える本文の run, run の親の段落)。"""
    found = {}
    body = root.find(w("body"))
    for para in body:
        for run in para.findall(w("r")):
            for el in run.iter():
                if slotlib.local(el) == "docPr" and el.get("id"):
                    found.setdefault(int(el.get("id")), (run, para))
    return found


def apply_recipe(package: DocxPackage, root: ET.Element, recipe: dict) -> list[ET.Element]:
    """原本にレシピを当てる。戻り値は原本の段落番号で引ける段落の並び（消した段落は None）。"""
    body = root.find(w("body"))
    paras = list(body)
    for index, expect in recipe.get("原本の確認", {}).items():
        got = _text(paras[int(index)])
        if expect not in got:
            raise RecipeError(f"原本の段落 {index} が想定と違います（{expect!r} を含むはず: {got[:30]!r}）。"
                              "レシピを作った原本と同じファイルか確かめてください。")

    shapes = _runs_with_docpr(root)
    for sid in recipe.get("取り除く図形", {}).get("id", []):
        if sid not in shapes:
            raise RecipeError(f"取り除く図形 id={sid} が原本にありません")
        run, para = shapes[sid]
        if run in list(para):
            para.remove(run)

    for sid, target in recipe.get("錨を移す", {}).items():
        if not sid.isdigit():
            continue
        if int(sid) not in shapes:
            raise RecipeError(f"錨を移す図形 id={sid} が原本にありません")
        run, para = shapes[int(sid)]
        para.remove(run)
        paras[int(target)].append(run)

    for sid, spec in recipe.get("位置を固定", {}).items():
        if not sid.isdigit():
            continue
        run, _ = shapes[int(sid)]
        anchor = next(el for el in run.iter() if slotlib.local(el) == "anchor")
        for axis, values in spec.items():
            pos = next(el for el in anchor if slotlib.local(el) == f"position{axis}")
            pos.set("relativeFrom", values["relativeFrom"])
            for child in list(pos):
                pos.remove(child)
            key = "align" if "align" in values else "posOffset"
            ET.SubElement(pos, f"{{{WP_NS}}}{key}").text = str(values[key])

    for index in recipe.get("セクション記号を外す段落", {}).get("段落", []):
        ppr = paras[index].find(w("pPr"))
        sect = ppr.find(w("sectPr")) if ppr is not None else None
        if sect is None:
            raise RecipeError(f"段落 {index} にセクション記号がありません")
        ppr.remove(sect)

    breaks = recipe.get("改ページ", {})
    for index in breaks.get("段落", []):
        para = paras[index]
        ppr = para.find(w("pPr"))
        if ppr is None:
            ppr = ET.Element(w("pPr"))
            para.insert(0, ppr)
        if ppr.find(w("pageBreakBefore")) is None:
            at = sum(1 for c in ppr if slotlib.local(c) in _BEFORE_PAGE_BREAK)
            ppr.insert(at, ET.Element(w("pageBreakBefore")))
    for index in breaks.get("取り除く段落", []):
        para = paras[index]
        if _text(para).strip() or slotlib.has_layout(para):
            raise RecipeError(f"段落 {index} は空行ではないので取り除けません")
        body.remove(para)
        paras[index] = None

    drop_unused_media(package, root)
    drop_embedded_fonts(package)
    return paras


def drop_unused_media(package: DocxPackage, root: ET.Element) -> None:
    """取り除いた図形の画像を、関係ごとパッケージから消す（挿絵を配らないため）。"""
    rels_name = "word/_rels/document.xml.rels"
    used = {v for el in root.iter() for k, v in el.attrib.items() if k.startswith("{%s}" % REL_NS)}
    rels = package.parts[rels_name].decode("utf-8")
    kept_targets = set()

    def keep(m: re.Match) -> str:
        rid = re.search(r'Id="([^"]+)"', m.group(0)).group(1)
        target = re.search(r'Target="([^"]+)"', m.group(0)).group(1)
        if "/image" in m.group(0) and rid not in used:
            return ""
        kept_targets.add(target)
        return m.group(0)

    rels = re.sub(r"<Relationship [^>]*/>", keep, rels)
    package.parts[rels_name] = rels.encode("utf-8")
    for name in list(package.names):
        if name.startswith("word/media/") and name[len("word/"):] not in kept_targets:
            package.names.remove(name)
            del package.parts[name]


def drop_embedded_fonts(package: DocxPackage) -> None:
    """埋め込みフォントを外す。

    原本は UD デジタル教科書体などのサブセットを埋め込んでいた。フォントのデータを
    リポジトリで配らないよう外す。Windows 10 以降には同じ書体が入っているので、
    Word で開いたときの見た目は変わらない。
    """
    for name in list(package.names):
        if name.startswith("word/fonts/") or name == "word/_rels/fontTable.xml.rels":
            package.names.remove(name)
            del package.parts[name]
    table = package.parts["word/fontTable.xml"].decode("utf-8")
    table = re.sub(r"<w:embed(Regular|Bold|Italic|BoldItalic)\b[^>]*/>", "", table)
    package.parts["word/fontTable.xml"] = table.encode("utf-8")
    settings = package.parts["word/settings.xml"].decode("utf-8")
    settings = re.sub(r"<w:(embedTrueTypeFonts|saveSubsetFonts|embedSystemFonts)\b[^>]*/>", "", settings)
    package.parts["word/settings.xml"] = settings.encode("utf-8")


def mark_regions(paras: list[ET.Element], recipe: dict) -> tuple[list[dict], list[slotlib.Slot]]:
    """区画の段落に目印を置き、区画表とスロットを返す。"""
    registry: dict[str, str] = {}
    definitions: dict[str, dict] = {}
    found: list[slotlib.Slot] = []
    sheets = []
    for sheet in recipe["sheets"]:
        regions, prototypes, fixed = {}, {}, []
        for name, (start, end) in sheet["区画"].items():
            members = [p for p in paras[start:end + 1] if p is not None]
            # 空行の基準書式は、区画で最も多く使われている文字書式
            tally: Counter = Counter()
            for para in members:
                for run in para.findall(w("r")):
                    if slotlib.is_plain_text_run(run) and slotlib.run_text(run).strip():
                        props = rpr.to_dict(run.find(w("rPr")))
                        tally[json.dumps(props, sort_keys=True)] += len(slotlib.run_text(run))
            fallback = json.loads(tally.most_common(1)[0][0]) if tally else {}
            ids = []
            for para in members:
                slot = slotlib.mark_paragraph(para, "s%04d" % (len(found) + 1),
                                              registry, definitions, fallback)
                found.append(slot)
                ids.append(slot.slot_id)
                if slotlib.has_layout(para) and name not in fixed:
                    fixed.append(name)
            regions[name] = ids
            proto = sheet.get("見本の段落", {}).get(name)
            if proto is not None:
                if not start <= proto <= end:
                    raise RecipeError(f"{sheet['名前']}・{name} の見本の段落 {proto} が区画の外です")
                prototypes[name] = ids[[i for i in range(start, end + 1) if paras[i] is not None].index(proto)]
        sheets.append({"名前": sheet["名前"], "区画": regions, "見本": prototypes, "行数固定": fixed})
    for slot in found:
        used = {p.span for p in markup.parse(slot.text)[0] if p.span}
        slot.extra_spans = {n: definitions[n] for n in sorted(used) if n in definitions}
    return sheets, found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", help="元にするプリント（docx）")
    parser.add_argument("--name", default="授業プリント", help="テンプレートの名前")
    parser.add_argument("--out", help="テンプレートを書き出す場所（既定: template/<名前>）")
    parser.add_argument("--stripped", help="レシピを当てただけの docx の書き出し先")
    parser.add_argument("--data", help="元のプリントの中身を教材形式で書き出す先")
    args = parser.parse_args(argv)

    recipe_dir = ROOT / "template" / args.name
    recipe = json.loads((recipe_dir / "recipe.json").read_text(encoding="utf-8"))
    tdir = Path(args.out) if args.out else recipe_dir

    package = DocxPackage(args.source)
    root = package.parse_document()
    try:
        paras = apply_recipe(package, root, recipe)
    except RecipeError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 1
    if args.stripped:
        stripped = copy.deepcopy(package)
        stripped.set_document(root)
        stripped.save(args.stripped)

    sheets, found = mark_regions(paras, recipe)
    package.set_document(root)
    package.save(tdir / "base.docx")

    shared: dict[str, dict] = {}
    for slot in found:
        shared.update(slot.extra_spans)
    _dump(tdir / "spans.json", {
        "説明": "書式表。原本に残る細かな書式の差（書式NN）と、スロットごとの上書き。"
                "教材データで使う名前付きの書式（囲み・太字・囲み太字・大・小・黒）は src/gendaiprint/rpr.py にある。",
        "共通": shared,
        "スロット別": {s.slot_id: s.local_spans for s in found if s.local_spans},
    })
    _dump(tdir / "defaults.json", {s.slot_id: s.text for s in found})
    _dump(tdir / "regions.json", {
        "説明": "区画表。教材形式の JSON は、プリント名（①〜④）と区画名でこの表を引いて流し込む。"
                "『見本』は行数を変えるときに写す段落、『行数固定』は図形と組になっていて行数を変えられない区画。",
        "元のプリント": Path(args.source).name,
        "sheets": sheets,
    })

    texts = {s.slot_id: s.text for s in found}
    content, blank = {}, {}
    for sheet in sheets:
        body, empty = {}, {}
        for name, ids in sheet["区画"].items():
            lines = [texts[i] for i in ids]
            body[name] = lines[0] if len(ids) == 1 else lines
            empty[name] = f"（{name}）" if len(ids) == 1 else [f"（{name}）"] + [""] * (len(ids) - 1)
        content[sheet["名前"]], blank[sheet["名前"]] = body, empty
    meta = {"テンプレート": f"template/{args.name}"}
    if args.data:
        _dump(Path(args.data), {"meta": {**meta, "題名": Path(args.data).stem},
                                "options": {"answer_mode": "原本どおり"}, "sheets": content})
    blank_path = (tdir if args.out else ROOT / "data") / f"_雛形_{args.name}.json"
    _dump(blank_path, {
        "meta": {**meta, "題名": "（教材名）"},
        "options": {"answer_mode": "原本どおり"},
        "_記法": {
            "{語}": "答え（赤字）。配布用（--answers 空欄）では白字になって空欄に見える",
            "{{語}}": "隠し答え（白字）",
            "_語_": "傍線",
            "<<囲み|語>>": "囲み（意味・理由・脚問 などの見出し）",
            "<<太字|語>>": "太字（【例１】【主張１】 など）",
            "<<囲み太字|語>>": "囲み＋太字（主張①・答・第一段）",
            "<<大|語>> / <<小|語>>": "11pt / 9pt",
            "行頭の全角スペース": "字下げ",
        },
        "sheets": blank,
    })

    for sheet in sheets:
        print(f"■ {sheet['名前']}")
        for name, ids in sheet["区画"].items():
            mark = "　※行数固定" if name in sheet["行数固定"] else ""
            print(f"    {name}: {len(ids)} 行{mark}")
    print(f"→ {tdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
