# GitHub Actions からの旧サイト公開

この経路は既存の `scripts/legacy_publish.py` の固定マニフェスト検査、HTTPS事前照合、FTPS上の対象読戻し、既存対象の事前バックアップ、最後のHTTPS全対象読戻しを使う。新規記事と訂正記事の対象制約も既存コードで検査する。通常の `--publish` とWindows確認画面は変更していない。

公開候補は `legacy-publication/bundles/<英数字で始まるID>/` に置く。ディレクトリには `manifest.json`、`stage/`、`baseline/` だけを含め、メール、資格情報、`data/`、ログ、サーバー設定、未確認ファイルは含めない。記事訂正は既存のcorrection manifestが定める対象のみを使い、画像や導線は同じハッシュの場合だけスキップする。

masterへのbundle追加・更新で事前検査が動く。差分が単一bundleに限定され、パスとmanifest SHAが一致し、現在の公開HTTPS内容がmanifestの基準と一致する場合だけ、`legacy-publish` Environmentを参照する送信jobに進む。Environmentの承認後、同じcommitとmanifest SHAだけを送る。手動実行でもbundle pathとmanifest SHAの両方を入力し、同じ検査を通す。FTPSに接続する前にActions実行、master ref、Environment marker、環境Secretの存在を確認する。値はコマンド引数・出力・ログに含めない。

**利用開始前に必要な管理者設定**: GitHubの `legacy-publish` Environment にrequired reviewersを設定し、`SAKURA_FTPS_PASSWORD` をEnvironment secretとして登録する。workflow、publisher、bundleをmasterへ入れる権限もレビュー対象として保護する。これらのGitHub設定はこの変更では行わず、Secret値も登録していない。承認者要件がないEnvironmentは承認ゲートにならないため、設定確認前に実送信してはならない。

送信後のmanifest-bound backupとreceiptはActions artifactに7日間保存する。HTTPS最終読戻しに失敗した実行は失敗として扱い、自動再送しない。結果が不明なときは公開URLと保存receiptを照合し、同一manifestの再送を避ける。

## サイト全体のGit管理

現時点の比較では、公開例会年次一覧と `src/content/reikai` は概ね同じ年度を持つが、1992年資料と2026年3月15日資料は一覧に見当たらず、公開状態を別途判定する必要がある。`public/reikai` は4,753ファイルで、24枚の美の山記事画像も含む。画像全件の本番bytes/hash、孤立ファイル、公開ルート外のサーバーデータまでは照合していない。トップページのカテゴリはAstro routesとして管理される一方、公開サーバーの旧HTML全量をGitが完全再現するとは未確認。

安全な移行には、後日、許可された読み取り専用の公開ツリー目録を取得し、URL、サイズ、SHA-256、ページからの参照状況で分類する。公開対象だけを段階的に追加し、非公開資料、秘密、設定、ログ、バックアップ、孤立ファイルは個別確認まで除外する。全量同期や削除を行わず、毎回manifestの明示対象だけを公開する。
