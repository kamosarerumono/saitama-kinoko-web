# GitHub Actions からの旧サイト公開

この経路は既存の `scripts/legacy_publish.py` の固定マニフェスト検査、HTTPS事前照合、FTPS上の対象読戻し、既存対象の事前バックアップ、最後のHTTPS全対象読戻しを使う。新規記事と訂正記事の対象制約も既存コードで検査する。通常の `--publish` とWindows確認画面は変更していない。

## 通常公開の担当判断と承認範囲

本人が依頼した通常の記事追加・訂正は、担当が内容と検証結果を確認し、このHPの依頼対象へ公開する。記事ごとに本人への追加確認やEnvironmentの承認待ちを必須とはしない。依頼のない記事、別の送信先、対象制約を超える訂正や全量同期には、この承認を適用しない。原稿・写真・公開差分の確認とmanifestへの固定は引き続き必要。

GitHubのrequired reviewersはEnvironment側の任意の保護設定であり、このworkflowとpublisherが検査する必須条件ではない。現在のEnvironmentに保護ルールがある場合はそのルールに従い、迂回しない。Secretの登録や認証設定・保護設定・アクセス範囲の変更は通常記事公開の承認とは別に扱う。この手順の整合修正では、それらの設定変更や本番公開・試運転を行わない。

Windowsで本人が起動する `--publish` は、[既存の手動手順](legacy-publication.md)どおり端末と確認画面を必要とする。Actions経路の通常公開方針を理由に、その確認機構を無効化しない。

## bundleの検証と送信

公開候補は `legacy-publication/bundles/<英数字で始まるID>/` に置く。ディレクトリには `manifest.json`、`stage/`、`baseline/` だけを含め、メール、資格情報、`data/`、ログ、サーバー設定、未確認ファイルは含めない。記事訂正は既存のcorrection manifestが定める対象のみを使い、画像や導線は同じハッシュの場合だけスキップする。

masterへのbundle追加・更新で事前検査が動く。変更されたbundleが1つで、パスとmanifest SHAが一致し、現在の公開HTTPS内容がmanifestの基準と一致する場合だけ、`legacy-publish` Environmentを参照する送信jobに進む。設定済みのEnvironment保護ルールを満たした後、同じcommitとmanifest SHAだけを送る。承認待ちのルールがなければ記事ごとの承認待ちは発生しない。手動実行でもbundle pathとmanifest SHAの両方を入力し、同じ検査を通す。FTPSに接続する前にActions実行、master ref、Environment marker、環境Secretの存在を確認する。値はコマンド引数・出力・ログに含めない。

**利用開始前の確認**: 対象の依頼、内容・差分のレビュー、通常のGit採用条件、`legacy-publish` Environmentと `SAKURA_FTPS_PASSWORD` Environment secretの準備状況を確認する。Secretが渡らなければpublisherは停止する。Secret名の存在は認証成功や公開完了の証明ではない。workflowは依頼の有無や内容レビューの完了を判定しないため、担当がその根拠と対象commit・manifest SHAを照合してから進める。未確認の設定を設定済みと仮定せず、必要な設定変更は別途扱う。required reviewersの追加やブランチ保護変更を、この文書修正の前提として新たに要求しない。

送信後のmanifest-bound backupとreceiptはActions artifactに7日間保存する。HTTPS最終読戻しに失敗した実行は失敗として扱い、自動再送しない。結果が不明なときは公開URLと保存receiptを照合し、同一manifestの再送を避ける。

## サイト全体のGit管理

現時点の比較では、公開例会年次一覧と `src/content/reikai` は概ね同じ年度を持つが、1992年資料と2026年3月15日資料は一覧に見当たらず、公開状態を別途判定する必要がある。`public/reikai` は4,753ファイルで、24枚の美の山記事画像も含む。画像全件の本番bytes/hash、孤立ファイル、公開ルート外のサーバーデータまでは照合していない。トップページのカテゴリはAstro routesとして管理される一方、公開サーバーの旧HTML全量をGitが完全再現するとは未確認。

安全な移行には、後日、許可された読み取り専用の公開ツリー目録を取得し、URL、サイズ、SHA-256、ページからの参照状況で分類する。公開対象だけを段階的に追加し、非公開資料、秘密、設定、ログ、バックアップ、孤立ファイルは個別確認まで除外する。全量同期や削除を行わず、毎回manifestの明示対象だけを公開する。
