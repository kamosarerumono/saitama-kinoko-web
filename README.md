# 埼玉きのこ研究会 HP管理

**現行サイト**: https://www.ippon.sakura.ne.jp/  
**現在の方針（2026-10-23）**: 現行さくらHTMLと既存URLを維持する。まず現状の復元可能なバックアップを揃え、その後にスマホ表示・観察会報告の更新手順を小さく改善する。

今回の新規取得は188ファイル保存後に停止しており、全体バックアップは未完了。実修正・削除・公開・移転は再開していない。[保全状況・復元条件・改善案](docs/plans/server-cleanup-20261019.md)を現在の入口とする。

**保存する旧案**: 同じrepoのAstro + Cloudflare Pages案。ソース・写真・lockfile・branch/PR履歴を保持する。現在のホスティング接続状態は未確認で、停止・廃止・移転の操作はしていない。Gitだけで現行旧サイト全体を復元できる状態とも扱わない。

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

## 旧Astro案の開発入口

以下は保存するAstro案の開発手順。依存追加・buildは書込みを伴い、バックアップや現行legacy全体の検証の代わりにはならない。今回これらのコマンドは実行していない。

```bash
npm install
npm run dev      # 開発サーバー起動
npm run build    # 本番ビルド
npm run preview  # ビルド結果プレビュー
```
