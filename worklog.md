# worklog

## 2026-06-18 メール/ドメイン調査 + HP更新手順の定型化
- 心配されていた「さくら×Cloudflareのドメイン問題でメール不達」は構造上起きないと実測確認: 両サイトとも各社サブドメイン(pages.dev / ippon.sakura.ne.jp)で独自ドメイン不在、ippon.sakura.ne.jpのMXはさくら自身で正常、会の連絡は個人ISPメール。
- HP更新手順を docs/HP更新手順.md に定型化。新サイト(§1-3=md追加+git push自動反映 / 行事予定だけevents.astro直書き)＋旧さくら(§4=SFTP手動、実構成を実測: 例会報告は houkoku_reikai.htm→YYYYreikaihoukoku.html→個別の3階層、行事予定は綴りgyouZiyotei、2017一覧は綴りミス、対応表§4-F)。栗原代表宛「更新終わりました」メールはGmailに下書き作成済(自動送信不可のため送信は本人操作)。
- 文字コード訂正反映: 旧サイトは「Shift_JIS固定」ではなくファイル混在(index.htm/会報=Shift_JIS, 行事予定=UTF-8)。メモリ reference-sakura-sftp の訂正を手順書§4-0/§5に反映。
- 残課題: events.astro が「2025年度」表記のまま要更新。新サイト独自ドメインは未取得(E-1/E-2)。docs/HP更新手順.md は未commit。会報36/37号のサーバ最終アップは手作業残。

## 2026-06-18 旧サイト行事予定2026年度版を作成
- 本番 2025gyouziyotei.html(UTF-8)を土台に、ユーザー提供の2026年度テキストで 2026gyouziyotei.html を作成。TOP index.htm(Shift_JIS)のリンクを2025→2026に更新。docs/plans/gyouji2026/ に格納。
- 年号タイポ補正: 原文「秋ヶ瀬2025/11/3・発表会2024/12/6・栽培2026/3/14」を曜日アンカーで 2026/11/3(火)・2026/12/6(日)・2027/3/14(日) に補正。kurihara メールは原文so-et→本番既存の so-net を維持。
- 残課題: 2ファイルを sakura へSFTP手動アップ(gyouji_yotei/2026gyouziyotei.html と www直下 index.htm)。傷害保険リンク hoken_onegai 2025.html は2026版が必要か要確認。総会はテキスト未記載のため未掲載。

## 2026-06-17 会報いっぽん36/37号に表紙を追加
- 35号同様の表紙画像を生成（Word .docm から部品抽出→Pillowで合成）し、docs/plans/ippon36g.html・37g.html に組込。SCAN00053.jpg(36)/SCAN00054.jpg(37) を新規作成。
- 発見: docs/plans のローカルドラフト2本は日本語が U+FFFD で破損していたため、本番sakuraの正常Shift_JIS版を土台に作り直した（構造BR数は本番と一致を確認）。
- 残課題: 4ファイル(html2/jpg2)を sakura サーバ backnumber/ へアップロードするのはユーザー手作業。
