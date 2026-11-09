#!/usr/bin/env python3
"""『空白の意味』授業プリントの図解・挿絵を描く。

    python3 figures/空白の意味/make_figures.py

このフォルダに 名前.svg / .png（答えは赤字）と、_空欄・_黒 の版ができる。
寸法（幅×高さ mm）は data/空白の意味.json の「図」と合わせてある。
答えの文字は白地の上に置く（灰色の地だと配布用の白字がうっすら見えるため）。

松林図屏風の実物の画像はここでは描かない。③ の図は「画面構成」を説明するための模式図で、
実物は教科書 p.146〜147 の図版（または東京国立博物館の画像）を見せる。
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "tools"))

from zukai import GRAY, Figure  # noqa: E402


def gauge() -> Figure:
    """① ワーク 空白うめたい度計（31mm 幅）。合計点が高いほど空白を埋めたくなる。"""
    return Figure.gauge("空白うめたい度計", [
        (21, 24, "うめつくし派", ["空白は", "もったいない"]),
        (16, 20, "ちょっと苦手派", ["空白は", "少し不安"]),
        (11, 15, "バランス派", ["埋めるも", "残すも"]),
        (6, 10, "余白たのしみ派", ["空白に", "想像が広がる"])])


def bowl() -> Figure:
    """① 第一段 空っぽの器（23mm 幅）。"""
    f = Figure(230, 760)
    cx = 115
    f.text(cx, 30, "空っぽの器", size=24, bold=True)
    f.line(20, 55, 210, 55, width=2)
    f.bowl(cx, 150, s=1.6)
    f.text(cx, 125, "？", size=40, bold=True)
    f.arrow(cx - 30, 270, cx - 60, 330)
    f.arrow(cx + 30, 270, cx + 60, 330)
    f.text(cx - 62, 365, "✕", size=30)
    f.lines(cx - 62, 430, ["無価値", "と見る"], size=20)
    f.text(cx + 62, 365, "○", size=30)
    f.lines(cx + 62, 420, ["何かが", "入る"], size=20)
    f.ans(cx + 62, 482, "予兆", size=20)
    f.lines(cx + 62, 540, ["と", "見立てる"], size=20)
    f.box(cx, 670, 210, 120, r=12)
    f.mixed(cx, 650, [("創造性", True), "が"], size=20)
    f.text(cx, 690, "空白に力を与える", size=20)
    return f


def pines() -> Figure:
    """② 第二段 精緻な松と荒い筆遣いの松（30mm 幅）。"""
    f = Figure(300, 1300)
    cx = 150
    f.text(cx, 30, "どちらが「松」らしい？", size=22, bold=True)
    f.line(20, 55, 280, 55, width=2)
    f.pine(cx, 520, s=1.6, style="fine")
    f.lines(cx, 575, ["精緻な描写", "（北宋画ふう）"], size=22)
    f.line(30, 650, 270, 650, width=1.5, dash=True)
    f.pine(cx + 40, 1150, s=1.0, style="mist")
    f.pine(cx - 20, 1170, s=1.7, style="rough")
    f.lines(cx, 1220, ["荒い筆遣い", "（南宋画・等伯ふう）"], size=22)
    return f


def kanizsa() -> Figure:
    """② ワーク 見えない三角形（カニッツァの三角形、37mm 幅）。"""
    f = Figure(370, 780)
    cx = 185
    f.text(cx, 30, "見えない三角形", size=26, bold=True)
    f.line(20, 55, 350, 55, width=2)
    f.kanizsa(cx, 330, 150)
    f.text(cx, 600, "白い三角形が", size=24)
    f.text(cx, 640, "見えるだろうか？", size=24)
    f.text(cx, 720, "（カニッツァの三角形）", size=18)
    return f


def screen() -> Figure:
    """③ 第三段 松林図の画面構成（模式図、78mm 幅）。"""
    f = Figure(780, 760)
    f.text(390, 32, "松林図の画面構成（模式図）", size=28, bold=True)
    f.line(30, 60, 750, 60, width=2)
    f.box(390, 380, 740, 560, r=4, width=2)            # 屏風の画面
    f.mountain(300, 300, 200, 110)                     # 霊峰（白の中の白）
    for x, s, style in ((150, 0.55, "mist"), (470, 0.6, "mist"), (620, 0.5, "mist")):
        f.pine(x, 470, s=s, style=style)               # 遠い松（霞む）
    for x, s in ((90, 1.15), (660, 1.25)):
        f.pine(x, 640, s=s, style="rough")             # 近い松（濃い）
    f.pine(400, 650, s=0.85, style="rough")
    # 見出し
    f.line(300, 185, 300, 160, width=1.5)
    f.text(300, 140, "霊峰＝「白の中の白」", size=22, bold=True)
    f.text(300, 112, "（最も遠い遠景）", size=18)
    f.line(540, 330, 600, 230, width=1.5)
    f.lines(640, 205, ["白い空間", "＝濃密な奥行き"], size=20, gap=1.3)
    f.line(90, 600, 160, 690, width=1.5)
    f.text(200, 705, "近景の濃い松", size=20)
    f.text(600, 705, "霞む松（遠景へ）", size=20)
    f.mixed(390, 740, ["白い空間は", ("不在", True), "ではない"], size=22, bold=True)
    return f


def aesthetic() -> Figure:
    """④ 第四段 逆説的な絵画表現と、身の回りの「空白」（47mm 幅）。"""
    f = Figure(470, 1500)
    cx = 235
    f.text(cx, 35, "空白に意味を読む", size=28, bold=True)
    f.line(40, 62, 430, 62, width=2)
    f.box(cx, 150, 300, 70, r=12)
    f.text(cx, 150, "何もない空白", size=26)
    f.arrow(cx, 195, cx, 255)
    f.text(cx + 70, 225, "かえって", size=20)
    f.box(cx, 320, 420, 90, r=12, width=4)
    f.mixed(cx, 320, ["豊かな", ("イマジネーション", True)], size=24)
    f.mixed(cx, 410, ["＝", ("逆説", True), "的な絵画表現"], size=24, bold=True)
    f.line(40, 470, 430, 470, width=1.5, dash=True)
    f.text(cx, 505, "身の回りの「空白」", size=24, bold=True)
    f.vase(120, 760, s=1.2)
    f.lines(120, 815, ["一輪挿し", "花のまわりの空間"], size=18)
    f.stone_garden(350, 680, 170, s=1.0)
    f.lines(350, 815, ["石庭", "白砂の余白"], size=18)
    f.person(110, 960, s=0.8)
    f.person(230, 960, s=0.8)
    f.balloon(170, 905, 110, 44, "……", tail=(0, 1), size=22)
    f.lines(170, 1105, ["会話の「間」", "沈黙も伝わる"], size=18)
    f.box(350, 1010, 150, 150, r=6, dash=True, stroke=GRAY)
    f.lines(350, 1010, ["ほかにも", "探そう"], size=20, colour=GRAY)
    f.box(cx, 1300, 420, 230, r=16, width=4)
    f.text(cx, 1225, "日本の美意識の一端", size=24, bold=True)
    f.text(cx, 1280, "空白地帯を", size=22)
    f.mixed(cx, 1325, ["情報の", ("ゼロ地帯", True), "と"], size=22)
    f.text(cx, 1370, "見なさない", size=22)
    return f


FIGURES = {"図0_空白うめたい度計": gauge, "図1_空っぽの器": bowl, "図2_松の描き比べ": pines,
           "ワーク2_見えない三角形": kanizsa, "図3_松林図の画面構成": screen, "図4_空白に意味を読む": aesthetic}

if __name__ == "__main__":
    png = "--no-png" not in sys.argv
    for name, make in FIGURES.items():
        for path in make().save(HERE / name, png=png):
            print(f"→ {path.relative_to(HERE.parents[1])}")
