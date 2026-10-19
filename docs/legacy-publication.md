# 新しい例会報告を、現在のさくらサイトへ掲載する

対象は**新規の例会報告1件**。既存URL・過去記事・さくらホストを保持する。全件移行、CMS、Gmail取得、無人公開、サーバー整理の実行は含まない。

## 本人の操作

担当が原稿・写真・公開差分を準備して確認後、出力フォルダの `PUBLISH_REPORT.cmd` を本人がダブルクリックする。日本語画面で対象記事・送信先・ファイル数を確認し「はい」で今回だけ公開する。記事ごとに準備した別の送信リストを使う。登録済み資格情報は本人起動の転送処理内だけで利用し、未登録なら非表示入力。AIへパスワードを渡さない。

登録/削除は、既存Windows用 `scripts/windows_credential.py register` / `delete` を本人の対話端末から実行する。既存の識別名 `GT030:FTPS:ippon.sakura.ne.jp:ippon`、AYUMI-D/kamos、このPC限定保存を維持する。同じWindowsユーザーの他プロセスも取得し得る。登録だけでは送信しない。

## 担当の準備（認証・送信なし）

1. 既存 `receive` → `prepare-draft` / `verify-draft`、Wordレビューを再利用する。保留を消さない。人が確認済みの `src/content/reikai/YYYY-MM-DD-name.md` と `public/reikai/YYYY/` の掲載用写真を使用する。通常のAstro buildも確認する。
2. 現行 `index.htm` と該当年別一覧を、公開HTTPSまたは既存の信頼できる読戻しから原バイトで保存する。文字コード・SHA256・挿入箇所を確認する。新年度の一覧/年ディレクトリ作成や既存記事の訂正はこの入口の対象外。
3. 私有 `data/` 配下で次のspecを作る。原稿と写真のSHAは人が確認した時点に固定する。公開前に画像が変われば停止する。

```json
{
  "schema_version": 1,
  "review_reference": "今回の原稿・写真・公開差分を確認した記録",
  "source": {
    "path": "src/content/reikai/2026-11-03-example.md",
    "sha256": "確認済みMarkdownのSHA256"
  },
  "legacy_slug": "261103_example",
  "assets": {"/reikai/2026/example.jpg": "確認済み画像のSHA256"},
  "navigation": {
    "annual": {"file": "annual.html", "sha256": "取得時SHA256", "encoding": "utf-8", "anchor": "取得HTML中の一意な挿入位置"},
    "top": {"file": "top.htm", "sha256": "取得時SHA256", "encoding": "cp932", "anchor": "取得HTML中の一意な挿入位置"}
  }
}
```

既存の私有draftを入力するときは `source-root` をそのbundleにし、`draft_review: "review.json"` を指定する。held/更新操作/対象hash不一致は拒否する。DBの最新状態との照合は先に既存 `verify-draft` で行う。手作業でレビューした原稿の場合も、review_referenceと全入力hashの確認は必須。

```text
python scripts/legacy_bundle.py --spec data/review/spec.json --source-root . --input-root data/review --output data/review/bundle --node <Node実行ファイル>
```

Windows上で実行すると、そのPythonとpublisherの位置を固定した本人用 `.cmd` も生成される。生成後にPython・repoを移動した場合は再準備する。出力先は実運用ではGit追跡外の `data/` を使用し、原本・spec・取得ページを公開ディレクトリへ置かない。

MarkdownはAstro既存の `@astrojs/markdown-remark` で解釈し、同じ原稿から旧HTMLを生成する。記事の外枠は直近の公開済み美の山記事の色・幅・表スタイルを再利用。掲載用画像は別の生成コピーを作るだけで原本を加工しない。旧URLは `reikai/YYYY/YYMMDD_name.html`。新規画像はその記事専用ディレクトリへ置く。TOP/年別一覧は指定位置への追記だけで、それ以外のバイト・文字コード・既存リンクを変更しない。アンカーがない/複数ある場合は停止する。

見出し・本文・表・箇条書き・JPEG/PNGを対象とし、未知のHTML、スクリプト、外部画像等は停止する。DOCX/XLSX原本、Office抽出、写真の掲載可否判断をこの処理で自動化しない。

## 検証・公開・再開

準備結果に `manifest_sha256` が出る。stageは写真→記事→年間一覧→TOPの順で固定され、追加ファイル・変更・別host・過去記事更新を拒否する。

```text
python scripts/legacy_publish.py --bundle data/review/bundle --manifest-sha <表示されたSHA>
python scripts/legacy_publish.py --bundle data/review/bundle --manifest-sha <表示されたSHA> --readback
```

引数なしのモードは認証なしHTTPS事前確認、`--readback` は公開側の全件照合。`--publish` は本人の実端末と明示クリック必須。TLS/ホスト名検証、暗号化データ接続を保持する。HTTPS照合不能なら安全側で停止し、FTPだけで公開成功としない。

初回公開/再開とも既存対象をFTPSで読み、未知の内容・権限拒否・HTTPS差異を拒否。全バックアップ確認後に残りを送る。記事と写真の全HTTPS一致を確認してから年間一覧・TOPを更新する。最後の全件HTTPS一致だけが成功。

記録は `data/legacy-publication/runs/<manifest SHA>/<実行日時>/`。各実行のバックアップは別フォルダへ排他的に作成し、上書きしない。共通lockで同じpublisherの二重実行を防ぐ。既存の別公開ツールも同時起動しない。

途中失敗は工程・対象path・FTP動詞だけを記録し、秘密・応答本文・例外本文を記録しない。自動再接続/無限再試行/自動巻戻しはしない。再開時は同一manifestの過去完了記録と現状を照合し、一致分を省略する。確認済みファイルの消失/変更や途中書込による未知hashは停止し、本人へ報告する。

## GT030との関係

受付台帳、衝突保持、Wordレビュー、draft作成を置換しない。既存の「draftから旧HTML/TOP/年別一覧へ」と「記事専用publisherの使い回し」が不足していた部分を補う。Gmail取得・定期実行・Discord通知の全体ACを完了とは扱わない。美の山の既存privateツール/原本/復旧証拠は変更せず、次の新規記事からこの共通入口を使う。

## 実装時の確認（2026-10-19）

- 新規生成・公開処理26テスト、Windows資格情報ラッパーの模擬11テストが成功。原稿/写真変更、保留draft、パス逸脱、文字コード維持、1〜3月の前年度扱い、既存バックアップ非上書き、途中EOF、同時編集、再開時スキップ、公開前リンク抑止を確認。
- 既存受付/Word/draftの58テスト中57成功、antiword実CLI依存の1件skip。受付本体は変更していない。
- 実Astro MarkdownレンダラーとCLIで私有の合成bundleを生成。独立headless Edgeの1280/390pxで画像欠け0・横はみ出し0。実cmd起動は非対話入力を認証前に拒否することを確認。
- Astro build 306ページ成功。会報collectionが空という既存warningあり。初回buildはtelemetry設定保存先のsandbox拒否で停止し、当該実行だけtelemetryを無効にして成功。権限設定は変更していない。
- 本番の資格情報取得・FTPS接続・送信はしていない。共通処理の本番成功を模擬試験から主張しない。
