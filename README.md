# あそびば — やっつの扉

つくったゲームの本棚。GitHub Pages で遊べます：https://iz3ico.github.io/app/

| フォルダ | 内容 |
|---|---|
| `index.html` | トップ（あそびば — やっつの扉）— `top_template.html` から `tools/build_top.py` で生成 |
| `bokyaku/` | 忘却の都市 — しずんだ街を、ただ、あるく |
| `hoshiyomi/` | 星詠みガチャ — 星霊と魔女の森 |
| `yumenofuchi/` | 夢のふち — 霧の交差点・壁紙の丘・雲の上をさまよう一人称ホラー |
| `neontrace/` | NEON TRACE — 屋上から標的を狙う3Dスナイパー。STAGE 01 ネオン街区・STAGE 02 硝子都市（`voice/` にオペレーター音声） |
| `dreamscape/` | DREAMSCAPE — 白い建築と水の3Dウォーキング。広間の先に、ループする迷宮（白い門・青の回廊） |
| `nchomechopo/` | んちょめちょぽ — もちもちの芽を操作する三人称3Dアクション。STAGE 1 そよかぜの丘（モデルは index.html に内蔵） |
| `atelier/` | MY LITTLE ATELIER — レンガとアーチ窓のアトリエで描く3Dお絵描きシミュレーション。鉛筆・水彩・油絵・パステル、作品は額縁に飾れる |
| `taketori/` | 竹取物語 — 一人称で竹を切りまくる3D探索。光る竹の手がかりを集めて霧の結界を越え、かぐや姫を探す。100本ごとに刃物が進化 |
| `assets/` | トップのサムネイル |
| `qr/` | トップと各ゲームの QR コード（`tools/make_qr.py` で生成） |

## ゲームを追加するとき
1. `新しいフォルダ/index.html` を置く
2. `assets/<id>.jpg` にサムネイル（960×540）を置く
3. `top_template.html` の `GAMES` に 1 行追加
4. `python3 tools/build_top.py` でトップを作り直す
5. 必要なら `tools/make_qr.py` に追加して QR を作り直す
