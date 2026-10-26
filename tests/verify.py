#!/usr/bin/env python3
"""検証一式。変更したら必ず通す。

    python3 tests/verify.py                       # テンプレートと教材データの検証
    NUKUMI_DOCX=原本.docx python3 tests/verify.py   # 原本からの作り直しと 1 ドット比較も

テンプレート（授業プリント・ワークシート）と、それぞれの教材データ（病と科学）について確かめる。

1. 原本（環境変数 NUKUMI_DOCX）があれば、レシピからテンプレートを作り直して、
   リポジトリのテンプレートと同じになること。さらに「テンプレート＋原本の文言」が
   「原本にレシピを当てただけのもの」と 1 ドットも変わらないこと（LibreOffice があれば）
2. 教材データが組めて、目印の取り残し・空のスロットが無く、各ページの横幅の見積もりが
   本文領域に収まること。教材データに書いた枚数の図が入ること
3. --answers の各指定で、消えるべき色の文字が 0 字になること
4. 表記チェックに ✗ が無いこと
5. LibreOffice があれば、4 ページ（①〜④）に収まること（目安）
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import build  # noqa: E402
from gendaiprint import figures as figlib  # noqa: E402
import check  # noqa: E402
import make_template  # noqa: E402

# (テンプレート名, 教材データ)
CASES = [("授業プリント", ROOT / "data" / "病と科学.json"),
         ("ワークシート", ROOT / "data" / "ワークシート_病と科学.json")]
FAILED: list[str] = []


def ok(cond: bool, label: str) -> None:
    print(("  ✓ " if cond else "  ✗ ") + label)
    if not cond:
        FAILED.append(label)


def document(path: Path) -> str:
    return zipfile.ZipFile(path).read("word/document.xml").decode("utf-8")


def coloured_chars(xml: str, colour: str) -> int:
    count = 0
    for run in re.findall(r"<w:r>.*?</w:r>|<w:r [^>]*>.*?</w:r>", xml, re.S):
        if f'w:val="{colour}"' in (re.search(r"<w:rPr>.*?</w:rPr>", run, re.S) or [""])[0]:
            count += sum(len(t.strip()) for t in re.findall(r"<w:t[^>]*>([^<]*)</w:t>", run))
    return count


def figure_images(docx: Path) -> set[bytes]:
    with zipfile.ZipFile(docx) as zf:
        return {zf.read(n) for n in zf.namelist() if n.startswith("word/media/zukai")}


def figure_specs(data_path: Path) -> list[dict]:
    data = json.loads(data_path.read_text(encoding="utf-8"))
    return [item for regions in data["sheets"].values() for value in regions.values()
            for item in (value if isinstance(value, list) else [value]) if figlib.is_figure(item)]


def expected_images(data_path: Path, mode: str) -> set[bytes]:
    data = json.loads(data_path.read_text(encoding="utf-8"))
    out = set()
    for regions in data["sheets"].values():
        for value in regions.values():
            for item in value if isinstance(value, list) else [value]:
                if figlib.is_figure(item):
                    stem = ROOT / Path(item["図"]).with_suffix("")
                    out.add(stem.with_name(stem.name + figlib.VARIANT[mode] + ".png").read_bytes())
    return out


def render(docx: Path, out: Path) -> list[Path] | None:
    if not (shutil.which("soffice") and shutil.which("pdftoppm")):
        return None
    out.mkdir(parents=True, exist_ok=True)
    subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", str(out), str(docx)],
                   check=True, capture_output=True)
    pdf = out / (docx.stem + ".pdf")
    # PPM（画素だけの形式）で書き出すので、ファイルの中身をそのまま比べられる
    subprocess.run(["pdftoppm", "-r", "60", str(pdf), str(out / docx.stem)], check=True)
    return sorted(out.glob(docx.stem + "*.ppm"))


def same_pixels(a: list[Path], b: list[Path]) -> bool:
    return len(a) == len(b) and all(x.read_bytes() == y.read_bytes() for x, y in zip(a, b))


def check_case(tmp: Path, name: str, data_path: Path, source: str | None) -> None:
    template = ROOT / "template" / name
    tmp.mkdir(parents=True, exist_ok=True)
    print(f"■ {name}（{data_path.name}）")
    print("1. 原本からの作り直し")
    if source and Path(source).exists():
        remade = tmp / "template"
        stripped = tmp / "stripped.docx"
        data = tmp / "nukumi.json"
        code = make_template.main([source, "--name", name, "--out", str(remade), "--stripped", str(stripped),
                                   "--data", str(data)])
        ok(code == 0, "レシピが原本に当たる")
        ok(document(remade / "base.docx") == document(template / "base.docx"),
           "作り直したテンプレートがリポジトリのものと同じ")
        for part in ("spans.json", "regions.json", "defaults.json", "figure.xml"):
            ok((remade / part).read_text(encoding="utf-8") == (template / part).read_text(encoding="utf-8"),
               f"{part} が同じ")
        rebuilt = tmp / "nukumi_rebuilt.docx"
        build.build(data, rebuilt)
        a, b = render(stripped, tmp / "r_stripped"), render(rebuilt, tmp / "r_rebuilt")
        if a is None:
            print("  - LibreOffice が無いので画像の比較は省略")
        else:
            ok(same_pixels(a, b), "テンプレート＋原本の文言が、原本（レシピ適用）と 1 ドットも変わらない")
    else:
        print("  - 原本が無いので省略（NUKUMI_DOCX=原本.docx で実行すると確かめる）")

    print("2. 教材データを組む")
    out = tmp / "out.docx"
    report = build.build(data_path, out)
    xml = document(out)
    ok("⟦" not in xml, "目印の取り残しが無い")
    ok(not report["missing"], "値の無いスロットが無い" + (f": {report['missing']}" if report["missing"] else ""))
    ok(not report["blank"], "空欄の区画が無い" + (f": {report['blank']}" if report["blank"] else ""))
    for sheet, (before, after) in report["amount"].items():
        print(f"     分量（{sheet}）: 原本 {before:.0f} 行分 → {after:.0f} 行分（参考）")
    limit = build.volume.PAGE_WIDTH_MM - build.volume.SAFETY_MM
    for sheet, used in zip(report["amount"], report["widths"]):
        ok(used <= limit, f"横幅（{sheet}）が本文領域に収まる（{used:.0f}／{limit:.0f}mm）")
    want = len(figure_specs(data_path))
    got = len(report.get("figures", []))
    ok(got == want, f"図が {want} 枚入る（{got} 枚）")
    ok(not report.get("warnings"), "図の幅・高さの警告が無い" + (f": {report.get('warnings')}" if report.get("warnings") else ""))
    ok("ぬくみ" not in xml, "前の教材の題名が残っていない")

    print("3. 解答の見せ方")
    red = coloured_chars(xml, "FF0000")
    ok(red > 0, f"原本どおり: 赤字の答えがある（{red} 字）")
    for mode, gone in (("空欄", "FF0000"), ("黒", "FF0000"), ("答え", "FFFFFF")):
        path = tmp / f"{mode}.docx"
        build.build(data_path, path, mode)
        left = coloured_chars(document(path), gone)
        ok(left == 0, f"{mode}: {gone} の文字が 0 字（{left} 字）")
        ok(figure_images(path) == expected_images(data_path, mode),
           f"{mode}: 図はこの見せ方の版（{figlib.VARIANT[mode] or '赤字'}）")

    print("4. 表記チェック")
    errors, notes = check.check(data_path)
    ok(not errors, f"✗ が無い（✗ {len(errors)} 件 / △ {len(notes)} 件）")
    for line in errors:
        print("     " + line)

    print("5. ページ数（目安）")
    pages = render(out, tmp / "r_out")
    if pages is None:
        print("  - LibreOffice が無いので省略")
    else:
        ok(len(pages) == 4, f"LibreOffice で {len(pages)} ページ（①〜④ の 4 ページ）")
    print()


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="gendai-verify-"))
    source = os.environ.get("NUKUMI_DOCX")

    for name, data_path in CASES:
        check_case(tmp / name, name, data_path, source)

    shutil.rmtree(tmp, ignore_errors=True)
    print()
    print("すべて通りました" if not FAILED else f"✗ {len(FAILED)} 件失敗")
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
