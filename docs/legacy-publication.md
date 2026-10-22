# 新しい例会報告を、現在のさくらサイトへ掲載する

本人が依頼した通常の記事追加・訂正は、担当が内容と検証結果を確認して進め、記事ごとの本人への追加確認を必須とはしない。Actions経路の対象範囲、検証、Environment設定との関係は[GitHub Actionsからの旧サイト公開](gha-ftps-publication.md)に従う。以下の本人操作・確認画面の説明は、Windowsの手動 `--publish` 経路の仕様であり、Actions経路にも毎回の本人操作を要求するものではない。認証設定・保護設定・アクセス範囲の変更は別途扱う。

## 通常の Git 保存と送信先確認

通常の feature 保存では、現在の branch 名と push 先 branch 名を一致させます。たとえば `feature/topic` の upstream が誤って `origin/master` なら、push を止めて upstream を確認し、送信先を直してから続けます。feature branch を `master` / `main` へ直接送る操作は拒否します。承認済みの merge は既存 PR 経由で行い、revert は意図した branch と完全 ref を確認して既存の finalize 手順に従います。

この repository の pre-push guard を有効にする設定は一度だけ行います。remote URL は対象 repository と完全一致させ、認証値を含む URL は使いません。

```text
git config --local codex.pushGuard.expectedRemote https://github.com/kamosarerumono/saitama-kinoko-web.git
git config --local core.hooksPath .githooks
```

通常の finalize 直前に、branch、remote、source/destination の完全 ref、source SHA を確認します。hook は実際の Git push から remote 名・URL・source ref/SHA・destination ref を受け取り、設定済み repository と照合します。`origin/master` を upstream にした feature branch は、どちらの refspec を指定しても fail closed します。初回 push で upstream がまだない branch は、同名 branch への完全 refspec のみ通ります。hook は push を実行せず、PR merge や同名 master/main の更新を禁止しません。remote が不明、ref が省略・不一致、SHA が変化した場合は停止して最新状態を読み直します。

回帰テスト `python -m unittest tests.test_git_push_guard` は一時 bare repository に実際の pre-push hook を設定し、feature→master の拒否と remote ref 不変、origin/master upstream の拒否、正しい同名 feature push、同名 master maintenance push、remote identity 不一致を確認します。本番 remote には接続しません。

このWindows手動経路の新規記事入口は**新規の例会報告1件**を対象とする。既存URL・過去記事・さくらホストを保持する。全件移行、CMS、Gmail取得、無人公開、サーバー整理の実行は含まない。

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

既存記事の訂正は新規記事の公開と区別し、訂正bundleが示す対象HTML 1件だけを更新する。画像24件と年間一覧/TOPの2件はhash一致を検査し、変更も再送もしない。bundleを再生成して訂正対象やhashを変えない。実行前にremoteとHTTPSの現状を読み、既に訂正済みなら送信しない。全対象のバックアップ、対象HTMLのreceipt、完了後の全27件HTTPS読戻しを確認する。receiptがない/結果が不明なら再送せず、まず実行状態・progress・HTTPSの現状を照合する。

Windowsでは、生成済みの `PUBLISH_<記事>_CORRECTION.cmd` をログイン中の通常デスクトップでエクスプローラーから開く。CodexのPTY、非対話サービス、隠し起動からは開かない。表示された確認には対象HTMLの完全URL、更新1件・27件検査、画像/導線の一致条件、バックアップの説明がある。初期選択は No のままなので、内容が一致すると本人が確認した場合だけ Yes を押す。ダイアログが見えない、対象が違う、確認の前提が変わった場合は No/閉じるで終了し、別経路で起動・認証・再送しない。既存のTLSとホスト名検証、資格情報の内部利用を保ち、このWindows手動経路に確認機構を省略するモードは設けない。

一番手数の少ない正規操作は、この生成済みCMDをエクスプローラーで一度開き、記事内容を確認して Yes を押す方法。Windowsの対話デスクトップを操作できる正式なUI接続が使えない場合、ツールからダイアログを読んだり操作できると仮定せず、本人がその画面で操作する。

## GT030との関係

受付台帳、衝突保持、Wordレビュー、draft作成を置換しない。既存の「draftから旧HTML/TOP/年別一覧へ」と「記事専用publisherの使い回し」が不足していた部分を補う。Gmail取得・定期実行・Discord通知の全体ACを完了とは扱わない。美の山の既存privateツール/原本/復旧証拠は変更せず、次の新規記事からこの共通入口を使う。

## 実装時の確認（2026-10-19）

- 新規生成・公開処理26テスト、Windows資格情報ラッパーの模擬11テストが成功。原稿/写真変更、保留draft、パス逸脱、文字コード維持、1〜3月の前年度扱い、既存バックアップ非上書き、途中EOF、同時編集、再開時スキップ、公開前リンク抑止を確認。
- 既存受付/Word/draftの58テスト中57成功、antiword実CLI依存の1件skip。受付本体は変更していない。
- 実Astro MarkdownレンダラーとCLIで私有の合成bundleを生成。独立headless Edgeの1280/390pxで画像欠け0・横はみ出し0。実cmd起動は非対話入力を認証前に拒否することを確認。
- Astro build 306ページ成功。会報collectionが空という既存warningあり。初回buildはtelemetry設定保存先のsandbox拒否で停止し、当該実行だけtelemetryを無効にして成功。権限設定は変更していない。
- 本番の資格情報取得・FTPS接続・送信はしていない。共通処理の本番成功を模擬試験から主張しない。
