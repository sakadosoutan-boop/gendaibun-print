#!/usr/bin/env python3
"""教材データ（JSON）とテンプレートから、現代文の授業プリント（docx）を組む。

    python3 src/build.py data/病と科学.json -o build/病と科学.docx
    python3 src/build.py data/病と科学.json -o build/病と科学_配布用.docx --answers 空欄

--answers で解答の見せ方を切り替える。

  原本どおり  赤字の答えは赤字、白字の隠し答えは白字のまま（既定）
  答え        隠し答えも赤字にして、すべて見せる
  空欄        赤字の答えも白字にして、すべて空欄にする（配布用）
  黒          すべての答えを黒字にする（モノクロ印刷の解答例）
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gendaiprint import regions as regionlib, rpr, volume  # noqa: E402
from gendaiprint import slots as slotlib  # noqa: E402
from gendaiprint.docxpkg import DocxPackage, w  # noqa: E402

ANSWER_MODES = {
    "原本どおり": None,
    "答え": {"FFFFFF": "FF0000"},
    "空欄": {"FF0000": "FFFFFF"},
    "黒": {"FF0000": "000000", "FFFFFF": "000000"},
}


class BuildError(ValueError):
    pass


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _recolour_spans(spans: dict[str, dict], mapping: dict[str, str] | None) -> dict[str, dict]:
    """書式表の色を読み替える。囲みや太字はそのまま、色だけ差し替える。"""
    out = dict(spans)
    if not mapping:
        return out
    named = list(rpr.SEMANTIC_SPANS.items()) + list(rpr.LABEL_SPANS.items())
    for name, delta in named + list(spans.items()):
        colour = delta.get("set", {}).get("color")
        if colour is None:
            continue
        new = mapping.get(ET.fromstring(colour).get(w("val")))
        if new and name != "黒":
            out[name] = {**delta, "set": {**delta["set"], "color": rpr.colour_fragment(new)}}
    return out


def lines_of(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if not all(isinstance(v, str) for v in value):
        raise BuildError(f"行は文字列の並びで書いてください: {value!r}")
    return list(value)


def build(data_path: Path, out_path: Path, answers: str | None = None) -> dict:
    payload = _load(data_path)
    if not payload:
        raise BuildError(f"教材データが読めません: {data_path}")
    mode = answers or payload.get("options", {}).get("answer_mode", "原本どおり")
    if mode not in ANSWER_MODES:
        raise BuildError(f"解答の見せ方は {'・'.join(ANSWER_MODES)} のどれかです（{mode}）")

    tdir = Path(payload.get("meta", {}).get("テンプレート", "template/授業プリント"))
    if not tdir.is_absolute():
        tdir = ROOT / tdir
    if not (tdir / "base.docx").exists():
        raise BuildError(f"テンプレートが見つかりません: {tdir}")
    formats = _load(tdir / "spans.json")
    table = _load(tdir / "regions.json")
    defaults = _load(tdir / "defaults.json")

    package = DocxPackage(tdir / "base.docx")
    root = package.parse_document()
    caps = volume.capacities(root)
    amount: dict[str, list[int]] = {}      # プリントごとの [原本の行数, 今回の行数]
    local: dict[str, dict] = dict(formats.get("スロット別", {}))
    values: dict[str, str] = {}
    report = {"resized": [], "padded": [], "blank": []}

    if "slots" in payload:                       # スロット形式（原本の完全再現用）
        values = {s["id"]: s["text"] for s in payload["slots"]}
    else:                                        # 教材形式
        given = payload.get("sheets", {})
        known = [s["名前"] for s in table["sheets"]]
        for name in given:
            if name not in known:
                raise BuildError(f"テンプレートに無いプリントです: 「{name}」（使えるのは {'・'.join(known)}）")
        for sheet in table["sheets"]:
            data = given.get(sheet["名前"], {})
            for key in data:
                if not key.startswith("_") and key not in sheet["区画"]:
                    raise BuildError(f"{sheet['名前']}に「{key}」という区画はありません"
                                     f"（{'・'.join(sheet['区画'])}）")
            for region, ids in sheet["区画"].items():
                label = f"{sheet['名前']}・{region}"
                if region not in data:
                    report["blank"].append(label)
                    continue
                lines = lines_of(data[region])
                original = [defaults.get(i, "") for i in ids]
                proto = sheet["見本"].get(region)
                known_caps = [caps[i] for i in ids if i in caps]
                if known_caps:
                    # 行 k の字数は区画の k 行目の段落で数える（あふれた行は区画で多い字数）
                    usual = max(set(known_caps), key=known_caps.count)
                    per_line = [caps.get(i, usual) for i in ids]
                    per_line += [usual] * (len(lines) - len(per_line))
                    # 原本の空行には 1pt の段落記号で詰めたものがあるので、字の大きさで重みを付ける
                    weight = [min(1.0, usual / c) for c in per_line]
                    tally = amount.setdefault(sheet["名前"], [0.0, 0.0])
                    tally[0] += sum(volume.columns(t, c) * k for t, c, k in zip(original, per_line, weight))
                    if proto is not None and lines != original:
                        tally[1] += sum(volume.columns(t, usual) for t in lines)
                    else:
                        tally[1] += sum(volume.columns(t, c) * k for t, c, k in zip(lines, per_line, weight))
                    tally[1] += max(0, len(ids) - len(lines))     # 空行で取っておく分
                if len(lines) > len(ids) and region in sheet["行数固定"]:
                    raise BuildError(f"「{label}」は図形と組になっているので {len(ids)} 行までです"
                                     f"（{len(lines)} 行あります）")
                if len(lines) < len(ids):
                    # 行が少ないときは空行で場所を取っておく（後ろの脚問や枠が寄ってこない）
                    report["padded"].append(f"{label} {len(lines)}/{len(ids)} 行（残りは空行）")
                    lines = lines + [""] * (len(ids) - len(lines))
                if lines != original and proto is not None:
                    # 書式を見本の段落にそろえて作り直す（原本の行ごとの字下げを持ち込まない）
                    new = regionlib.resize(root, label, ids, len(lines), proto)
                    base = local.get(proto, {})
                    for i in new:
                        local.setdefault(i, base)
                    if len(lines) != len(ids):
                        report["resized"].append(f"{label} {len(ids)}→{len(lines)} 行")
                    ids = new
                elif len(lines) != len(ids):
                    ids = regionlib.resize(root, label, ids, len(lines))
                    report["resized"].append(f"{label} {len(ids)}→{len(lines)} 行")
                values.update(zip(ids, lines))

    mapping = ANSWER_MODES[mode]
    spans = _recolour_spans({**formats.get("共通", {}), **payload.get("spans", {})}, mapping)
    local = {k: _recolour_spans(v, mapping) for k, v in local.items()}
    report["missing"] = slotlib.fill(root, values, spans, local, mapping)
    slotlib.recolour_opaque(root, mapping)
    package.set_document(root)
    package.save(out_path)
    report.update(mode=mode, amount=amount)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("data", help="教材データ（JSON）")
    parser.add_argument("-o", "--out", required=True, help="出力する docx")
    parser.add_argument("--answers", choices=list(ANSWER_MODES), help="解答の見せ方")
    args = parser.parse_args(argv)

    try:
        report = build(Path(args.data), Path(args.out), args.answers)
    except (BuildError, regionlib.RegionError, KeyError) as e:
        print(f"✗ {e}", file=sys.stderr)
        return 1

    print(f"→ {args.out}（解答: {report['mode']}）")
    for line in report["resized"]:
        print(f"  行数を変えた区画: {line}")
    for line in report["padded"]:
        print(f"  空行で埋めた区画: {line}")
    if report["blank"]:
        print(f"  教材データに無いので空欄にした区画: {'、'.join(report['blank'])}")
    over = False
    for name, (before, after) in report["amount"].items():
        ratio = after / before * 100 if before else 0
        mark = "⚠ " if ratio > 100 else ""
        over |= ratio > 100
        print(f"  {mark}分量（{name}）: 原本 {before:.0f} 行分 → 今回 {after:.0f} 行分（{ratio:.0f}%）")
    if over:
        print("  原本より多い面があります。紙面からはみ出すおそれがあるので、行を減らすか"
              "短くしてください。最終確認は Word で。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
