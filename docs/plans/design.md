# 設計書

## 1. 技術アーキテクチャ

```
[Markdown/画像] → [Astro Build] → [静的HTML/CSS/JS] → [Cloudflare Pages CDN]
                                                            ↓
                                                    [ユーザーのブラウザ]
```

### 技術選定理由

| 技術 | 選定理由 |
|------|----------|
| **Astro** | コンテンツサイト最適。Content Collections で構造化管理。EmDashへの将来移行パスあり |
| **Tailwind CSS** | ユーティリティファーストでレスポンシブ対応が容易 |
| **Cloudflare Pages** | 無料・帯域無制限・CDN最速・SSL自動・git push自動デプロイ |
| **Markdown** | 記事追加が簡単。git管理と相性が良い |

## 2. ディレクトリ構造

```
saitama-kinoko-web/
├── src/
│   ├── content/              # コンテンツ（Markdown）
│   │   ├── config.ts         # Content Collections定義
│   │   ├── reikai/           # 例会報告
│   │   │   ├── 2025/
│   │   │   │   ├── 05-soukai.md
│   │   │   │   ├── 06-kawagoe.md
│   │   │   │   └── images/
│   │   │   ├── 2024/
│   │   │   └── ...（2000年まで）
│   │   ├── kaihou/           # 会報バックナンバー
│   │   │   ├── 035.md
│   │   │   └── ...
│   │   ├── news/             # お知らせ
│   │   └── pages/            # 静的ページ
│   │       ├── about.md      # 会について
│   │       ├── charter.md    # 会則
│   │       ├── join.md       # 入会案内
│   │       └── history.md    # あゆみ
│   ├── layouts/
│   │   ├── BaseLayout.astro  # 共通レイアウト
│   │   ├── ArticleLayout.astro
│   │   └── GalleryLayout.astro
│   ├── components/
│   │   ├── Header.astro
│   │   ├── Footer.astro
│   │   ├── Navigation.astro
│   │   ├── PhotoGallery.astro
│   │   ├── NewsCard.astro
│   │   └── Breadcrumb.astro
│   ├── pages/
│   │   ├── index.astro       # トップページ
│   │   ├── events.astro      # 行事予定
│   │   ├── reikai/
│   │   │   ├── index.astro   # 例会報告一覧
│   │   │   └── [...slug].astro
│   │   ├── kaihou/
│   │   │   ├── index.astro
│   │   │   └── [...slug].astro
│   │   ├── data/             # きのこ関連データ
│   │   ├── links.astro       # リンク集
│   │   └── about/
│   │       ├── index.astro
│   │       ├── charter.astro
│   │       └── join.astro
│   └── styles/
│       └── global.css
├── public/
│   ├── images/               # 共通画像
│   ├── downloads/            # ダウンロードファイル
│   │   ├── fungi_dic.zip
│   │   └── gaku_yomi.zip
│   └── favicon.ico
├── scripts/                  # 移行スクリプト
│   ├── convert_reikai.py
│   ├── convert_kaihou.py
│   └── optimize_images.py
├── docs/                     # プロジェクトドキュメント
│   └── plans/
├── astro.config.mjs
├── tailwind.config.mjs
└── package.json
```

## 3. コンテンツスキーマ

### 例会報告（reikai）

```yaml
---
title: "美の山公園観察会"
date: 2025-10-12
location: "秩父市美の山公園"
meetingPoint: "美の山公園第二駐車場"
participants: 25
memberCount: 19
dayMemberCount: 6
organizer: "栗原晴夫・近藤芳明"
reporter: "近藤芳明"
photographer: "河野茂樹"
images:
  - src: "./images/251012_01.jpg"
    caption: "集合写真"
  - src: "./images/251012_02.jpg"
    caption: "ヌメリスギタケモドキ"
speciesList:
  - "ヌメリスギタケモドキ"
  - "ナラタケ"
---

報告テキスト本文...
```

### 会報バックナンバー（kaihou）

```yaml
---
title: "いっぽん 第35号"
issueNumber: 35
publishDate: 2024-04-30
coverImage: "./covers/ippon35.jpg"
articles:
  - title: "記事タイトル"
    author: "著者名"
    page: 1
hasFullText: false  # 全文HTML掲載の有無
---
```

### お知らせ（news）

```yaml
---
title: "きのこ栽培勉強会の報告を更新しました"
date: 2026-04-10
---
```

## 4. デザイン方針

### カラースキーム

| 用途 | 色 | コード |
|------|-----|--------|
| プライマリ（深緑） | 森・自然 | #2d5016 |
| セカンダリ（茶） | 土・木 | #8B6914 |
| アクセント（オレンジ） | きのこ | #d26900 |
| 背景 | 和紙風 | #f5f0e8 |
| テキスト | 本文 | #333333 |
| リンク | 下線なし | #0000CC（旧サイト踏襲） |

### タイポグラフィ

- 見出し: Noto Sans JP（太字）
- 本文: system-ui, sans-serif（16px、行間1.8）
- 学名: serif（イタリック）

### レスポンシブブレークポイント

| 端末 | 幅 | レイアウト |
|------|-----|-----------|
| モバイル | 〜640px | 1カラム |
| タブレット | 641〜1024px | 2カラム |
| デスクトップ | 1025px〜 | メインコンテンツ + サイドバー |

### 写真ギャラリー

- グリッド表示（3列 / 2列 / 1列 レスポンシブ）
- クリックで拡大表示（ライトボックス）
- 遅延読み込み（lazy loading）
- WebP形式 + JPEG フォールバック

## 5. SEO対応

| 項目 | 実装 |
|------|------|
| meta description | 各ページ個別に設定 |
| OGP | og:title, og:description, og:image |
| sitemap.xml | Astro自動生成 |
| robots.txt | 全ページクロール許可 |
| 構造化データ | Organization, Event |
| canonical URL | 全ページに設定 |

## 6. ホスティング構成

```
[GitHub Repository] → push → [Cloudflare Pages Build] → [CDN配信]
                                                            ↓
                              [独自ドメイン] ← DNS ← [Cloudflare DNS]
```

### ドメイン戦略

1. Cloudflare Pagesデプロイ（`saitama-kinoko.pages.dev`で即公開）
2. 独自ドメイン取得・設定（`saitama-kinoko.org` 等）
3. 旧サイト（`ippon.sakura.ne.jp`）からリダイレクト設置
4. さくらインターネット解約（リダイレクト期間後）
