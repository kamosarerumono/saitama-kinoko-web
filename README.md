# 埼玉きのこ研究会 公式サイトリニューアル

**現行サイト**: https://www.ippon.sakura.ne.jp/  
**新サイト**: Astro + Cloudflare Pages（構築中）

## プロジェクト概要

1984年設立・会員約64名の「埼玉きのこ研究会」の公式サイトを、2000年開設の静的HTMLサイトからモダンなAstroベースのサイトにリニューアルするプロジェクト。

## 技術スタック

| 項目 | 選定 |
|------|------|
| フレームワーク | Astro |
| スタイリング | Tailwind CSS |
| ホスティング | Cloudflare Pages |
| コンテンツ管理 | Markdown + Astro Content Collections |
| デプロイ | git push → 自動ビルド・デプロイ |

## ドキュメント

- [要件定義](docs/plans/requirements.md)
- [設計書](docs/plans/design.md)
- [工程表・タスク一覧](docs/plans/tasks.md)
- [既存サイト調査レポート](docs/plans/site-audit.md)
- [並行運用計画](docs/plans/parallel-operation.md)

## 開発

```bash
npm install
npm run dev      # 開発サーバー起動
npm run build    # 本番ビルド
npm run preview  # ビルド結果プレビュー
```
