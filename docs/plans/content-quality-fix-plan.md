# コンテンツ品質修正計画

## 現状の問題

### 根本原因
旧HTMLが多重テーブルのレイアウト構造で、同一コンテンツが以下の形で重複:
1. **テーブル単位の重複**: 同じテーブルが2-3回出現（Table 2 = Table 3）
2. **セル内の重複**: 1つの`<td>`に本文+テーブルデータが全て入っている巨大セル
3. **行内の重複**: 同一行に2列あり、両方に同じテキスト

### 現在のmigrate_v2.pyの限界
- `body.descendants`走査で全セルのテキストを拾うため、重複列のテキストも含まれる
- テーブル構造の重複除去（`deduplicate_table_cells`）が不完全
- 本文テキストとテーブルデータが同一セルに混在するケースに対応できない
- 段落レベルの重複排除が文の途中で切れるケースに対応できない

## 新しいアプローチ案

### 方法: 2パス変換

**Pass 1: テキスト抽出（重複なし）**
```python
# body.get_text()で全テキストを取得
raw_text = body.get_text(separator='\n')

# 行単位で重複排除（連続する同一行を1つに）
lines = raw_text.split('\n')
deduped = []
for line in lines:
    stripped = line.strip()
    if stripped and (not deduped or stripped != deduped[-1]):
        deduped.append(stripped)
```

**Pass 2: テーブルデータ抽出（別途）**
```python
# 種類テーブルは body.find_all('table') から直接抽出
# 4列テーブル（五分類群/新目名/新科名/種名）のみ対象
for table in body.find_all('table'):
    rows = table.find_all('tr')
    first_row = [c.get_text(strip=True) for c in rows[0].find_all('td')]
    if '五分類群' in first_row or '科名' in first_row:
        # → Markdown テーブルに変換
```

**Pass 3: 画像抽出**
```python
# img src を収集（重複なし、拡張子正規化）
seen_imgs = set()
for img in body.find_all('img'):
    src = img.get('src', '')
    basename = os.path.basename(src)
    if basename not in seen_imgs:
        seen_imgs.add(basename)
```

**Pass 4: 組み立て**
```
frontmatter
---
本文テキスト（Pass 1）
画像（Pass 3）
確認種一覧（Pass 2）
文責
```

## 影響範囲

全240件のMarkdownファイルを再生成する。

影響が大きい（重複がひどい）年代:
- 2015-2018: MSO Word由来、最も品質が悪い（41件）
- 2019-2024: 比較的新しいが一部重複あり（約50件）
- 2009-2014: 中程度の品質問題（約60件）
- 2000-2008: 古い構造だが比較的シンプル（約80件）

## 作業手順

1. migrate_v3.pyを作成（2パス方式）
2. テスト: 問題のある代表5ファイルで検証
   - 2016/161103akigasekouen.html（本タスクの対象）
   - 2019/191006_minoyama.html（テーブル+本文混在）
   - 2015/151206kansatukai.html（MSO重度）
   - 2024/241006_minoyama.html（最新形式）
   - 2010/100725minoyama.html（中間期）
3. 検証OK → 全ファイル再生成
4. ビルド・デプロイ
5. ブラウザで各年代サンプル確認

## 見積もり
- スクリプト作成: 20分
- テスト・修正: 15分
- 全件再生成: 5分
- ビルド・デプロイ: 10分
- **合計: 約50分**
