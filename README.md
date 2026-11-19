# あそびば — いつつの扉

つくったゲームの本棚。GitHub Pages で遊べます：https://iz3ico.github.io/app/

| フォルダ | 内容 |
|---|---|
| `index.html` | トップ（あそびば — いつつの扉）— `top_template.html` から `tools/build_top.py` で生成 |
| `bokyaku/` | 忘却の都市 — しずんだ街を、ただ、あるく |
| `hoshiyomi/` | 星詠みガチャ — 星霊と魔女の森 |
| `yumenofuchi/` | 夢のふち — 霧の交差点・壁紙の丘・雲の上をさまよう一人称ホラー |
| `neontrace/` | NEON TRACE — ネオンの雨の街で、屋上から標的を狙う3Dスナイパー（`voice/` にオペレーター音声） |
| `dreamscape/` | DREAMSCAPE — 白い建築と水の3Dウォーキング。広間の先に、ループする迷宮（白い門・青の回廊） |
| `assets/` | トップのサムネイル |
| `qr/` | トップと各ゲームの QR コード（`tools/make_qr.py` で生成） |

## ゲームを追加するとき
1. `新しいフォルダ/index.html` を置く
2. `assets/<id>.jpg` にサムネイル（960×540）を置く
3. `top_template.html` の `GAMES` に 1 行追加
4. `python3 tools/build_top.py` でトップを作り直す
5. 必要なら `tools/make_qr.py` に追加して QR を作り直す
