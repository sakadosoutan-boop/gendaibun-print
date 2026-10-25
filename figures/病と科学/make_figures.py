#!/usr/bin/env python3
"""『病と科学』授業プリントの図解（①〜④ に 1 枚ずつ）を描く。

    python3 figures/病と科学/make_figures.py

このフォルダに 図N_名前.svg / .png（答えは赤字）と、_空欄・_黒 の版ができる。
答えの文字（赤字。配布用では白字）は白地の上に置く（灰色の地だと白字がうっすら見えるため）。
寸法（幅×高さ mm）は data/病と科学.json の「図」と合わせてある。幅は、図のために
空けた行の数 × 行の幅（①② は 6.2mm、③④ は 4.1mm）に収まるように決めている。
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "tools"))

from zukai import Figure  # noqa: E402


def fig1() -> Figure:
    """① 第一段 科学崇拝への道（23mm 幅）。"""
    f = Figure(230, 1300)
    cx = 115
    f.text(cx, 30, "科学崇拝への道", size=26, bold=True)
    f.line(20, 55, 210, 55, width=2)
    f.cloud(cx, 120, s=1.5)
    f.text(cx, 225, "不可解なもの", size=24)
    f.mixed(cx, 258, [("神", True), "の怒り"], size=24)
    f.arrow(cx, 285, cx, 335)
    f.germs(cx + 50, 350, s=0.7)
    f.microscope(cx - 30, 460, s=1.0)
    f.text(cx, 500, "病原菌の発見", size=24, bold=True)
    f.arrow(cx, 525, cx, 570)
    f.box(cx, 650, 210, 140, r=14)
    f.lines(cx, 625, ["科学によって", "理解できる"], size=24)
    f.mixed(cx, 685, ["＝", ("科学信仰", True)], size=24)
    f.arrow(cx, 725, cx, 770)
    f.person(cx, 805, s=1.1, coat=True)
    f.lines(cx, 960, ["医師が強い", "自信をもつ"], size=24)
    f.arrow(cx, 1000, cx, 1045)
    f.person(cx, 1080, s=1.1)
    f.mixed(cx, 1235, ["医師に", ("依存", True)], size=24)
    return f


def fig2() -> Figure:
    """② 第二段 病人と病気の切り離し（41mm 幅）。"""
    f = Figure(410, 1450)
    cx = 205
    f.text(cx, 35, "西洋医学の見方", size=28, bold=True)
    f.line(30, 62, 380, 62, width=2)
    f.ellipse(cx, 250, 185, 160, fill="#F4F4F4")
    f.text(cx, 125, "病人", size=30, bold=True)
    f.person(cx, 175, s=1.0, pain=True)
    f.lines(cx, 345, ["感覚・苦しみ", "個人差・生活"], size=24)
    f.line(15, 440, 395, 440, width=3, dash=True)
    f.scissors(40, 440, s=1.2)
    f.text(cx + 40, 470, "切り離し", size=26, bold=True)
    f.ellipse(cx, 640, 185, 145)
    f.text(cx, 535, "病気", size=30, bold=True)
    f.ellipse(cx, 660, 100, 68, fill="#E6E6E6")
    f.lines(cx, 660, ["測定・検査", "できる症状"], size=24)
    f.arrow(cx, 790, cx, 850)
    f.mixed(cx, 880, ["病気の", ("数値", True), "化"], size=26)
    f.monitor(cx, 1000, 300, 150, ["体温　36.8", "血圧　128／80", "血糖値　95"], size=24)
    f.arrow(cx, 1095, cx, 1150)
    f.box(cx, 1265, 380, 210, r=16)
    f.lines(cx, 1215, ["答えられない部分は", "切り捨てられる"], size=24)
    f.mixed(cx, 1300, ["医学が", ("人間", True), "を排除"], size=26, bold=True)
    f.text(cx, 1405, "※医学は万能という錯覚", size=22)
    return f


def fig3() -> Figure:
    """③ 第三段 痛みの否定と依存（55mm 幅）。"""
    f = Figure(550, 1450)
    cx = 275
    f.text(cx, 35, "痛みはだれのもの？", size=28, bold=True)
    f.line(40, 62, 510, 62, width=2)
    f.balloon(410, 120, 150, 56, "痛い！", tail=(0, 1))
    f.person(410, 195, s=1.15, pain=True)
    f.text(410, 360, "患者", size=26, bold=True)
    f.person(130, 195, s=1.15, coat=True)
    f.text(130, 360, "医師", size=26, bold=True)
    f.monitor(130, 470, 210, 110, ["データ上は", "異常なし"], size=24)
    f.lines(400, 470, ["間接的な", "データから", "痛みを判断"], size=22)
    f.arrow(cx, 545, cx, 600)
    f.box(cx, 665, 470, 110, r=14)
    f.mixed(cx, 645, ["患者の感覚を", ("否定", True)], size=26)
    f.text(cx, 690, "痛みを医師に取りあげられる", size=22)
    f.arrow(cx, 725, cx, 780)
    f.balloon(cx + 90, 815, 230, 52, "先生に任せよう", tail=(-1, 1), size=22)
    f.person(cx - 60, 860, s=1.05, sit=True)
    f.mixed(cx, 1035, ["医師への", ("依存", True)], size=26, bold=True)
    f.arrow(cx, 1065, cx, 1120)
    f.box(cx, 1235, 470, 210, r=16, width=5)
    f.text(cx, 1170, "病人から", size=24)
    f.mixed(cx, 1220, ["苦しみを", ("受容", True), "する"], size=26)
    f.text(cx, 1268, "能力が奪われていく", size=24)
    f.mixed(cx, 1315, ["依存性は", ("無能力", True), "へ"], size=24)
    f.text(cx, 1405, "※「自分の足で立つ」ことができない", size=22)
    return f


def fig4() -> Figure:
    """④ 第四段 科学の功罪と筆者の主張（47mm 幅）。"""
    f = Figure(470, 1450)
    cx = 235
    f.text(cx, 35, "科学の功罪", size=28, bold=True)
    f.line(40, 62, 430, 62, width=2)
    f.scale(cx, 120, s=1.35)
    f.text(cx - 110, 240, "功（利益）", size=24, bold=True)
    f.text(cx + 110, 240, "罪（弊害）", size=24, bold=True)
    f.lines(cx - 120, 360, ["病気の", "仕組みの解明", "中心静脈輸液", "超音波診断"], size=22)
    f.lines(cx + 110, 360, ["病名をつける", ("正常値", True), "「病人」の出現", "偏った医療"], size=22)
    f.line(cx, 290, cx, 540, width=1.5, dash=True)
    f.dna(70, 590, 220, s=1.1)
    f.lines(275, 660, ["遺伝子診断", "遺伝子治療", "クローン人間"], size=24)
    f.mixed(275, 760, ["経済的", ("利益", True)], size=24)
    f.text(275, 800, "と結びつくと危険", size=22)
    f.arrow(cx, 850, cx, 905)
    f.box(cx, 1130, 440, 420, r=18, width=5)
    f.text(cx, 950, "筆者の主張", size=26, bold=True)
    f.mixed(cx, 1010, ["科学の", ("限界", True), "を考え"], size=26)
    f.mixed(cx, 1065, ["人間の", ("限界", True), "をわきまえ"], size=26)
    f.mixed(cx, 1120, ["謙虚に", ("自然", True), "と"], size=26)
    f.text(cx, 1170, "向き合う", size=26)
    f.sprout(cx, 1300, s=1.4)
    return f


FIGURES = {"図1_科学崇拝への道": fig1, "図2_病人と病気の切り離し": fig2,
           "図3_痛みの否定と依存": fig3, "図4_科学の功罪": fig4}

if __name__ == "__main__":
    png = "--no-png" not in sys.argv
    for name, make in FIGURES.items():
        for path in make().save(HERE / name, png=png):
            print(f"→ {path.relative_to(HERE.parents[1])}")
