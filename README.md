# 埼玉きのこ研究会 HP管理

**現行サイト**: https://www.ippon.sakura.ne.jp/  
**現在の方針（2026-10-23）**: 現行さくらHTMLと既存URLを維持する。まず現状の復元可能なバックアップを揃え、その後にスマホ表示・観察会報告の更新手順を小さく改善する。

`/www` のスナップショット#2は13,301ファイルを私有保存し、別の復元用ZIPの標準展開・内容照合まで完了した。全サーバー保全・本番復旧・表示確認は未受入。展開物を動かさず分類目録を作り、既存Gitの2020/2019年度一覧を限定修正し、保存集合上の検証とGit配布rootの不足を分けて記録した。公開・削除・移転・master変更はしていない。[分類集計・修正根拠・残件](docs/plans/server-cleanup-20261019.md)を現在の入口とする。

**Astroはいったん退役**: 本人の新方針により、整備対象をさくらの現行HTML、保存正本をGitとする。通常npm入口 `dev/build/preview/astro` は外し、旧案のソース・写真・依存/lockfile・設定・branch/PR履歴は可逆に保持する。外部hosting/DNS・認証・security・料金は変更しておらず、接続状態は未確認。Git配布rootはまだ全現行HTML/依存を揃えていない。

## 保存する旧リニューアル案

1984年設立・会員約64名の「埼玉きのこ研究会」の公式サイトを、2000年開設の静的HTMLサイトからモダンなAstroベースのサイトにリニューアルするプロジェクト。

## 旧案の技術スタック（現行さくら公開の設定ではない）

| 項目 | 選定 |
|------|------|
| フレームワーク | Astro |
| スタイリング | Tailwind CSS |
| ホスティング | Cloudflare Pages |
| コンテンツ管理 | Markdown + Astro Content Collections |
| デプロイ | 当初案はgit push連携。現在の接続・配信状態は未確認 |

## ドキュメント

- [現在の保全・復元条件・HTML整理とスマホ改善案](docs/plans/server-cleanup-20261019.md)
- [現行legacy公開手順](docs/legacy-publication.md)
- [公開後の静的HTMLを基準にする準備手順](docs/minoyama-static-preparation.md)
- [要件定義](docs/plans/requirements.md)
- [設計書](docs/plans/design.md)
- [工程表・タスク一覧](docs/plans/tasks.md)
- [既存サイト調査レポート](docs/plans/site-audit.md)
- [並行運用計画](docs/plans/parallel-operation.md)
- [メール原稿受付（オフライン、公開権限なし）](docs/mail-intake.md)

## 現行HTMLの作業入口と旧案の保管

現行URLに対応する静的HTMLをGitで管理する。保存物の内容一致だけで配布rootの完成や公開可能性とは扱わず、参照先・構文・実表示・復元/rollbackを別に確認する。[今回の整理・検証と未達](docs/plans/legacy-html-cleanup-20261023.json)を参照。

Astroの開発・build・preview用npm scriptsは退役済みで、通常手順として実行しない。旧案の復元参照はmasterの基準commit `dd4b4bba6dbc44299577292b848f26e58288cecc` とする。この版にpackage/lockfile・src/・Astro/TS設定があり、現在保持中のソース/lockfile/設定と同一である。PRだけの中間commitの取得を復元の前提にしない。新規cloneの実行はしていない。依存追加・再install・build・旧案のhosting再開は今回行わない。

通常のローカル診断は正規worktreeのrootで `python scripts/check_legacy_html.py --baseline HEAD` を使う。Python 3.10以上の利用可能な実体を指定する。対象は既存Gitの年次一覧2件と川越見本だけで、変更を書き込まない。既知のGit配布参照不足と新規回帰、限定構文診断と未実施のSGML規格検証を別々に出力する。終了コード0でも規格/配布/表示の受入完了ではない。

本番置換は、整理・HTML構文/参照・実表示・復元/rollbackの検証完了後という条件付き。全削除先行はせず、正確な対象と手順を確認するまで本番操作・master更新を行わない。
