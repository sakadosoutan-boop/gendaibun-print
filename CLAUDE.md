# CLAUDE.md

益田先生の現代文プリント（A4横・縦書き、授業プリント①〜④）の組版を固定し、教材データ(JSON)を流し込んでプリント(docx)を作るテンプレート。原本は1学期の『ぬくみ』。古文プリント（sakadosoutan-boop/kobun-print）のやり方を受け継いでいる。詳細は README.md、設計の理由と原本で見つかった点は docs/設計メモ.md。

## 絶対ルール
- `template/*/base.docx` は手で編集しない。テンプレートを変えるときは原本 docx と `recipe.json` から `tools/make_template.py` で作り直す。
- 組版（図形・枠・段組・縦書き設定）は原本の XML をそのまま使う。OOXML を自前で組み立てて置き換えない。原本に手を入れるのはレシピに書いたことだけ。
- 変更後は必ず `python3 tests/verify.py` を通す（原本があれば `NUKUMI_DOCX=原本.docx` を付けて、作り直しと 1 ドット比較まで）。
- 外部パッケージを増やさない（Python 標準ライブラリのみ）。
- 図形入りの run の判定は局所名で行う（`mc:AlternateContent` は w: 名前空間ではない）。
- 縦書きでは、横位置が「段組（column）基準」の図形は錨の段落の行からの距離で置かれる。錨を別の段落へ移すときは、レシピの「位置を固定」で余白・ページ基準に置き直す。
- ページの頭は空行の数ではなく「段落前で改ページ」でそろえる。
- 原本 docx（図版を含む）・指導書 PDF・埋め込みフォントはリポジトリに入れない。
- 図解・挿絵は `figures/<教材>/make_figures.py`（部品は `tools/zukai.py`）で描き、教材データの区画の行に `{"図": …, "行": N, "幅": …, "高さ": …}` で入れる。答えの字は `ans()`／`mixed()` で書く（赤字・空欄・黒の 3 版になる）。図の幅は空けた行の字面だけの幅（①② 6.2mm／行、③④ 4.1mm／行）に収める。
- 紙面に収まるかは build の「横幅」（行の幅 1.39em で見積もり、266mm 以内）で見る。
- 新しい教材を書いたら `python3 tools/check.py data/○○.json` で、前の教材の文言が残っていないか確かめる。

## 構成
- `src/gendaiprint/` … docxpkg（入出力）/ rpr（書式差分・名前付き書式）/ markup（記法）/ slots（目印・流し込み）/ regions（区画の行数増減）/ volume（分量と横幅の見積もり）/ figures（図の差し込み）
- `src/build.py` … 教材データ＋テンプレート → docx（横幅の見積もり・図の差し込み・解答表示の切り替え付き）
- `template/授業プリント`（授業プリント型）と `template/ワークシート`（体感ワークシート型）。どちらも同じ原本から、それぞれの recipe.json で作る。verify は両方を確かめる。
- `tools/` … make_template（原本＋レシピ→テンプレート）/ check（表記チェック）/ zukai（図解・挿絵の SVG 部品）
- `figures/<教材>/` … make_figures.py と、描いた図（SVG・PNG、_空欄・_黒 の版）

## 検証コマンド
| コマンド | 内容 |
|---|---|
| `python3 tests/verify.py` | 一式（LibreOffice と poppler があればページ画像を比較） |
| `python3 tools/check.py data/*.json` | 表記チェック |

LibreOffice のページ割り・行送りは Word の目安にならない（UD デジタル教科書体が無いため。図も後ろの行にかぶって見える）。紙面に収まるかは build の「横幅」で見る。

## コミット規約
`feat:` / `fix:` / `docs:` / `chore:` ＋日本語要約。
