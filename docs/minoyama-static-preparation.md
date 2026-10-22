# 美の山の既存URLを保つ静的入力からの準備

対象は `https://ippon.sakura.ne.jp/reikai/2026/261004_minoyama.html` の既存1記事だけ。新記事、全サイト同期、配信先変更、原本の再取得、公開実行を含めない。今回追加した入口はローカル準備だけで、publisherやworkflowの起動条件・公開対象制約を変更しない。

## 保存証拠から確定した対応

2026-10-22の指定記事1回のHTTPS比較は18,804 bytes、SHA-256 `5820e9c9ed68b7e77a4f35c62a93785baed70c48aa21f481a289095abded6995` で保存済み公開後stageと一致した。保存manifestのSHA-256は `cc1a623611a30f6bad31c374b4f194785e7c1af35fbf65258917282b389fadd6`。対応する保存receiptは `PUBLICATION_VERIFIED`、27対象中記事1件送信・26件skipである。これは保存版と今回の指定記事比較の証拠であり、他URLの現在状態や将来の送信許可の証明ではない。

| 対象 | 静的入力rootからのパス＝既存公開パス | 基準と責任 |
|---|---|---|
| 記事 | `reikai/2026/261004_minoyama.html` | 公開後stageのUTF-8 bytesを基準とし、明示レビューした本文差分だけを候補にする |
| 画像24件 | `reikai/2026/images_261004/261004_minoyama-01.jpg`、02〜24は同名PNG | manifestの24パスとhashを維持。画像の追加・変更・改名は拒否 |
| 年間一覧 | `reikai/2026reikaihoukoku.html` | UTF-8、SHA-256 `7a4f04c47b02a06f5405876039c7f30c6062bc17351a5a35d317cf98a1435ea0`。既存href `2026/261004_minoyama.html` を保持 |
| TOP | `index.htm` | Shift_JIS（保存bytesはcp932で読取可）、SHA-256 `590b5df6021cff5c56f4f922d11c67c4218a1d18b3bfbdaac6961639696c0b5c`。既存導線のbytesを保持 |

既存記事の訂正なので、年間一覧・TOPへ新たに挿入する位置は設けない。新規記事用のanchorを推定して流用せず、この2ファイルはそのまま検査対象にする。記事のタグ・属性、style/scriptの内容、コメント・宣言も保存版から変更せず、本文テキストの差分だけを候補とする。CSS参照やmeta refresh等を新しい参照経路として混ぜない。

既存Gitの `public/reikai/2026/261004_minoyama-01.jpg`、02〜24のPNGは保存manifestの24画像hashと全件一致した。ただしGit内のこの平置きパスと、旧サイトの `images_261004/` 付きパスは異なる。内容一致をroute一致へ読み替えず、候補rootでは上表の旧公開パスを明示する。今回、画像の移動・複製・新しい正本への配置はしていない。

## 静的HTMLと生成物の責任分担

この旧URLには、受入済み静的HTMLを基準とする方式を選ぶ。現在の `docs/plans/minoyama2026/261004_minoyama.html` は19,200 bytes、SHA-256 `f0b2c26c10ef2bbe9e709abfea9920bfe19f99b8ad7e4ba0a59c297ca5851a1a` の訂正前資料であり、公開後の正本へ自動で戻さない。

`src/content/reikai/2026-10-04-261004_minoyama.md` はAstro経路の入力として保持する。`src/pages/reikai/[...slug].astro` はcollectionの `entry.id` をrouteへ渡す別経路であり、このMarkdownを旧HTMLとbyte同一の正本とは扱わない。既存旧URLのHTMLをAstroで再生成・置換せず、同じ出力パスへ静的HTMLと生成物の両方を書かせない。

将来Gitで静的入力を所有する場合は、既存 `public/` の該当公開パスを唯一の置き場とし、新しい全量ミラーを増やさない案が最小。ただし現時点の `public/` はこの旧URLのHTML・画像ディレクトリ構成をそろえて持っていないため、今回のコード変更で実データの配置やroute切替はしない。以下の `source-root` は、公開パスに対応した候補入力rootであり、repo全体を自動同期する指定ではない。

## 送信なしの準備入口

`scripts/legacy_static_bundle.py` は、固定SHAの既存correction bundleと、そのmanifestに結び付く完全な保存receiptを読み、候補rootの同じ27パスだけを検査する。周辺ファイルを走査・コピーしない。変更なしなら `NO_CHANGE` を返して出力を作らない。記事1件だけが変わり、画像・導線のbytesと上記HTML構造が変わらない場合だけ、既存publisher形式の `manifest.json` / `stage/` / `baseline/` を新しい出力先へ準備する。既存出力は上書きしない。

```text
python scripts/legacy_static_bundle.py --baseline-bundle <保存bundle> --baseline-manifest-sha <固定SHA> --receipt-run <同manifestの保存run> --source-root <静的候補root> --output <入力外の新規出力先> --review-reference <依頼と差分レビューの参照>
```

これは既存資料の出力先を示す形であり、新しい本番候補の作成・公開を依頼するものではない。実資料を使う場合も原本と保存receiptを保持し、パスや私有原文をGitへ転載しない。今回の実行検証は架空の27対象fixtureだけを使う。

出力の `PREPARED_OFFLINE` / `auto_publish=false` はローカル準備成功だけを表す。公開フラグやCMDは生成しない。既存publisherのローカルmanifest検査だけを再利用し、HTTPS・FTPS・資格情報・Actions実行へ接続しない。baselineの `before_sha256` は保存済み公開後stageのhashへ更新され、元manifest SHAとレビュー参照を出力へ結び付ける。

保存receiptは現在の本番状態や編集内容の正当性を保証しない。担当による依頼・内容・差分確認は引き続き必要。Git差分からこの入力を自動選択する接続、一般記事への拡張、実公開・Environment準備、元GT030のGmail実受付・定時接続は未受入のまま保持する。
