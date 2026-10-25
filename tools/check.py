#!/usr/bin/env python3
"""教材データの表記チェック。

    python3 tools/check.py data/病と科学.json

古文プリントで実際に起きた取りこぼし（前の教材の設問が残っていた、括弧の全角と
半角が混ざっていた など）と、『ぬくみ』原本で見つかった点を、新しい教材でも
拾えるようにしたもの。✗ は直すべきもの、△ は確かめてほしいもの。

  ✗ 前の教材の文言  テンプレートの元の教材（『ぬくみ』）の題名や行がそのまま残っている
  ✗ 参照ページ      （109・8）のような本文の参照が、meta の「ページ範囲」の外
  ✗ 段落の範囲      ① の段落表と、各ページの段見出しの範囲が食い違う
  ✗ 括弧            「」『』（）〈〉【】 の開き閉じが行の中でそろっていない
  ✗ 記法            {答え} などの記法が閉じていない
  △ 半角の括弧      ( ) が使われている（原本は全角が基本）
  △ 空の答え        {　} のように答えの中身が空白だけ
  △ 長い行          学習・脚問の行が 1 行（52 字）に収まらず折り返す
  ✗ 図              図の画像（答えが赤字・_空欄・_黒 の 3 版）が無い、寸法の指定が無い
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gendaiprint import markup  # noqa: E402

PAIRS = ["「」", "『』", "（）", "〈〉", "【】"]
REF_RE = re.compile(r"（(\d+)・(\d+)）")
RANGE_RE = re.compile(r"Ｐ([０-９]+)・Ｌ([０-９]+)\s*〜\s*(?:Ｐ([０-９]+)・Ｌ([０-９]+)|終わり)")
WIDE = str.maketrans("０１２３４５６７８９", "0123456789")
LINE_CHARS = 52
# 教材によらず同じ文言でよい行（見出しなど）
COMMON = {"", "　", "　<<大|設問>>", "　設問"}


def _lines(value) -> list[str]:
    if value is None:
        return []
    return [value] if isinstance(value, str) else list(value)


def check(path: Path) -> tuple[list[str], list[str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    errors: list[str] = []
    notes: list[str] = []
    tdir = ROOT / data.get("meta", {}).get("テンプレート", "template/授業プリント")
    defaults = json.loads((tdir / "defaults.json").read_text(encoding="utf-8"))
    regions = json.loads((tdir / "regions.json").read_text(encoding="utf-8"))
    old_lines = {v for v in defaults.values() if v not in COMMON}
    old_title = re.search(r"『([^』]+)』授業プリント", markup.plain(next(iter(defaults.values()))))
    old_title = old_title.group(1) if old_title else None
    pages = data.get("meta", {}).get("ページ範囲")

    ranges: dict[str, tuple] = {}
    table_rows: list[str] = []
    for sheet, regs in data.get("sheets", {}).items():
        for region, value in regs.items():
            for k, line in enumerate(_lines(value), 1):
                where = f"{sheet}・{region} {k} 行目"
                if isinstance(line, dict):          # 図
                    for suffix in ("", "_空欄", "_黒"):
                        png = ROOT / Path(line.get("図", "")).with_suffix("")
                        png = png.with_name(png.name + suffix + ".png")
                        if not png.exists():
                            errors.append(f"✗ 図  {where}: {png.relative_to(ROOT)} がありません"
                                          "（figures/…/make_figures.py で作る）")
                    for key in ("行", "幅", "高さ"):
                        if key not in line:
                            errors.append(f"✗ 図  {where}: 「{key}」がありません")
                    continue
                try:
                    text = markup.plain(line)
                except markup.MarkupError as e:
                    errors.append(f"✗ 記法  {where}: {e}")
                    continue
                if line in old_lines:
                    errors.append(f"✗ 前の教材の文言  {where}: テンプレートの元の行がそのまま残っています: {text[:30]}")
                if old_title and old_title in text:
                    errors.append(f"✗ 前の教材の文言  {where}: 『{old_title}』が残っています")
                for open_, close in PAIRS:
                    if text.count(open_) != text.count(close):
                        errors.append(f"✗ 括弧  {where}: {open_}{close} の数が合いません: {text[:30]}")
                if re.search(r"[()]", text):
                    notes.append(f"△ 半角の括弧  {where}: {text[:30]}")
                for piece in markup.parse(line)[0]:
                    if piece.span in ("ans", "hide") and not piece.text.strip("　 "):
                        notes.append(f"△ 空の答え  {where}")
                if pages:
                    for m in REF_RE.finditer(text):
                        if not pages[0] <= int(m.group(1)) <= pages[1]:
                            errors.append(f"✗ 参照ページ  {where}: （{m.group(1)}・{m.group(2)}）は"
                                          f" p.{pages[0]}〜{pages[1]} の外です")
                if region in ("学習", "脚問") and len(text) > LINE_CHARS:
                    notes.append(f"△ 長い行  {where}: {len(text)} 字（折り返して 2 行分になります）")
            if region == "段落表":
                table_rows = [markup.plain(x) for x in _lines(value) if isinstance(x, str)]
            if region == "段見出し":
                m = RANGE_RE.search(markup.plain(_lines(value)[0]))
                if m:
                    ranges[sheet] = tuple((g or "").translate(WIDE) for g in m.groups())

    # 段落表の k 行目と、k 枚目の段見出しの範囲を突き合わせる
    names = [s["名前"] for s in regions["sheets"]]
    for k, row in enumerate(table_rows):
        m = RANGE_RE.search(row)
        if not m or k >= len(names) or names[k] not in ranges:
            continue
        got = tuple((g or "").translate(WIDE) for g in m.groups())
        if got != ranges[names[k]]:
            errors.append(f"✗ 段落の範囲  ①・段落表 {k + 1} 行目 {got} と {names[k]}・段見出し "
                          f"{ranges[names[k]]} が食い違います")
    return errors, notes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("data", nargs="+", help="教材データ（JSON）")
    args = parser.parse_args(argv)
    failed = False
    for name in args.data:
        errors, notes = check(Path(name))
        print(f"■ {name}: ✗ {len(errors)} 件 / △ {len(notes)} 件")
        for line in errors + notes:
            print(f"  {line}")
        failed |= bool(errors)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
