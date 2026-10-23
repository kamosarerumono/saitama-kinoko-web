# 埼玉きのこ研究会 HP更新 手順書（定型化）

> 2026-10-24: Astroの通常入口は退役。現行さくらHTMLをGitで管理する。下記の旧Astro/Cloudflare並行運用手順は参考保管で、通常作業には使わない。hosting/DNS・認証/TLS/security設定は変更しない。
> 2026-10-19: 旧HTML生成・公開経路は[現行手順](legacy-publication.md)を参照。古いSFTP限定・--insecure・パスワード引数例は現行公開に使用しない。証明書検証を維持する。

最終更新: 2026-10-24

## 現在の作業方針

既存URL・写真・本文の意味を保ち、既存Gitの年次一覧と観察会報告見本を小さく整備する。Git保存は本番公開と別。構文/属性の限定診断、SGML規格適合、Git配布rootの参照成立、実表示、復元/rollbackを分けて確認する。[現在の計画と実測](plans/server-cleanup-20261019.md)に集約する。

Astroのコード・依存/lockfile・設定は保持する。復元参照はmasterの基準commit `dd4b4bba6dbc44299577292b848f26e58288cecc`。通常の開発起動設定から退役したastro-devを外し、.claude/launch.jsonに代替HTTPサーバーや成功stubは置かない。

<details>
<summary>退役したAstro案の旧手順（当時の§0〜1、参考保管）</summary>

最終更新: 2026-06-18

このファイルは「サイトをどう更新するか」を毎回ここだけ見れば済むようにまとめたものです。
技術用語は最小限にしています。**新サイト（§1〜3）と旧さくらサイト（§4）の両方**をカバーします。
並行運用中は、原則 **新サイトを先に更新 → 同じ内容を旧サイトにも反映** します。

---

## 0. いま動いているサイトは2つ（並行運用中）

| | 新サイト（メイン） | 旧サイト（さくら） |
|---|---|---|
| URL | https://saitama-kinoko.pages.dev | https://www.ippon.sakura.ne.jp/ |
| 仕組み | Astro + Cloudflare Pages | 手書きHTML |
| 更新方法 | **Markdownを足して `git push`**（自動公開） | SFTPで手動アップロード |
| 文字コード | UTF-8 | **Shift_JIS 固定** |
| 画像置き場 | `public/` 配下 | `/home/ippon/www/` 配下 |

新サイトは Markdown のほうが圧倒的に楽なので、**新→旧の順**にする。

---

## 1. よくある更新（新サイト）

更新の種類ごとに「どのファイルを足す／直すか」だけ覚えればOK。
**例会報告・お知らせ・会報・会員発信は、ファイルを置くと一覧とトップページに自動で出ます**（手動でリンクを足す必要なし）。
**行事予定だけは例外**で、プログラム（events.astro）を直接書き換えます。

### 1-A. 例会報告を追加する（年8回・最頻出）

1. 写真を置く（フォルダが無ければ作る）
   ```
   public/reikai/2026/1.jpg, 2.jpg, ...
   ```
2. 報告の Markdown を新規作成する
   ```
   src/content/reikai/2026-06-28-260628_kawagoe.md
   ```
   ファイル名は `日付-わかりやすい名前.md`。

3. 中身（先頭の `---` で囲む部分が「項目」、その下が本文）
   ```markdown
   ---
   title: "川越・狭山観察会（2026年6月28日）報告"
   date: 2026-06-28
   location: "川越市〜狭山市"
   reporter: "報告者の氏名"
   participants: 25
   ---

   <div class="grid grid-cols-2 gap-2 my-4">

   ![](/reikai/2026/1.jpg)

   ![](/reikai/2026/2.jpg)

   </div>

   ここに観察記録の本文を書く。
   ```
   - 必須は `title` と `date` の2つだけ。`location` `reporter` `participants` `organizer` `photographer` は任意。
   - 画像は本文中に `![](/reikai/2026/1.jpg)` の形（先頭の `/` を忘れない）。

4. 公開する（→ §3）。トップの「最新の例会報告」と `/reikai` 一覧に自動で出ます。

### 1-B. お知らせを更新する（月1〜2回）

1. Markdown を新規作成
   ```
   src/content/news/2026-06-20-koushin.md
   ```
2. 中身（本文は無くてもよい）
   ```markdown
   ---
   title: "2026年度の行事予定を公開しました"
   date: 2026-06-20
   tag: "NEW"
   ---
   ```
   - `tag` は `NEW` / `INFO` / `EVENT`（迷ったら `INFO`）。トップに**新しい順で5件**まで自動表示。

3. 公開する（→ §3）。

### 1-C. 行事予定を更新する（年1回・※ここだけ手順が特殊）

行事予定は Markdown ではなく **`src/pages/events.astro` の中の一覧（events = [...]）を直接書き換え**ます。

1. `src/pages/events.astro` を開く。
2. 先頭の `const events = [ ... ]` の中身を新年度に差し替える。1件はこの形：
   ```js
   {
     date: '2026年6月28日（日）', title: '川越・狭山観察会',
     area: '観察地域',
     meeting: '集合場所（住所）',
     schedule: '9:30集合 受付・概要説明後に観察。昼食12:00〜13:00、同定会13:00〜',
     organizer: '世話人氏名（代表）', done: false,
   },
   ```
   - `done: false` … これから開催（強調）。`done: true` … 終了済み（「終了」バッジ）。
3. 見出しの年度表記も直す（68行目あたり `2025年度 行事予定` → `2026年度`。**現状まだ2025年度のまま＝要更新**）。
4. 公開する（→ §3）。

### 1-D. 会報「いっぽん」のバックナンバーを追加する（年1回）

1. `src/content/kaihou/ippon-38.md` を作る
   ```markdown
   ---
   title: "会報いっぽん 第38号"
   issueNumber: 38
   publishDate: 2026-04-01
   hasFullText: false
   ---
   ```
   - `issueNumber`・`publishDate` は必須。
2. 表紙画像は `public/` 配下に置いて本文から参照。
3. 公開する（→ §3）。`/kaihou` に出ます。

### 1-E. 会員発信ページを追加する

`src/content/kaiinhassin/2026-06-01.md` を作る。`title`・`date`（必須）、`author`（任意）。

---

</details>

## 2. 更新前の限定ローカル検査

正規worktreeのrootで、利用中のPython 3.10以上の実体を指定する。Gitは2.48以上を明示要件とし、旧版/版判定不能ではHTML検査前に説明付きで停止する。`--no-lazy-fetch`を外す互換fallbackはしない。子プロセスにlazy fetch禁止と全transport禁止を指定し、欠落objectを取得しない。実機2.53.0.windows.3で確認し、2.43拒否/2.48対応経路はmockによる検証で、両版の実機試験ではない。[Git 2.48公式仕様](https://git-scm.com/docs/git/2.48.0)。

```text
python scripts/check_legacy_html.py --baseline HEAD
python -m unittest tests.test_legacy_html_checks tests.test_legacy_html_review_regressions -v
```

入口は既存Gitの2019/2020年度一覧と川越見本だけを読み、ファイルを書き換えず外部接続もしない。文字コードを宣言どおり厳格復号し、HTML4要素名・重複属性・TABLE/IMG等の限定属性・必須終了タグの一部とCSSの字句区切りを調べる。任意終了タグやTransitionalのFONT/CENTERをHTML5基準で一律改変しない。Git配布rootの既知の不足と新しい参照回帰を、ローカルの基準Git版と比較して別に出す。

charsetは有効なhead/prolog内のHTML4 Content-Type metaだけを採用し、コメント・CSS・script・TITLE・本文の文字列で代用しない。未宣言/無効/競合やUTF-8 BOMとの矛盾は推測復号せず停止。DOCTYPEも実際のprolog宣言を判定し、宣言キーワードの大小文字とPUBLIC識別子の完全一致を分ける。IMGのsrc/altとSTYLE/SCRIPTのtypeは値なしを検出するが、意図的な`alt=""`まで禁止しない。列挙したHTML4 URL属性は正確な配布pathで調べ、BASE・object/appletのcodebase/archive/classid・PARAM ref・refresh・data等の未対応意味はUNVERIFIEDにする。BASEがある相対参照を文書path基準で推測してprobeしない。`javascript:`等は実行せず診断とJS確認対象へ反映する。全参照解決の宣言ではなく、fragment・CSS依存・実表示等の範囲外も残る。[指摘別の正例/負例と記録の適用版](plans/legacy-checker-review-20261024.json)。

CSSの字句区切り検査は、文字列内だけでなく通常token中のbackslashに続く文字も区切りとして数えない。例えば`.foo\{bar { color: red; }`を誤って不均衡としない。完全CSS tokenizer/escape文法・値・cascade・表示は引き続き範囲外。[W3Cのescape説明](https://www.w3.org/TR/css-syntax-3/#escaping)を参照。

Git参照はpathだけでなくmodeも確認する。現indexは`ls-files --stage -z`のstage 0・100644/100755、基準treeはblobの100644/100755だけを通常ファイルとする。120000のsymlink entryはWindows等で通常ファイルに展開されていても解決済みにせず、未解決stageも除外する。選択元HTMLも現index・基準treeの双方で通常ファイルであることが必要。[Gitのstage出力](https://git-scm.com/docs/git-ls-files#Documentation/git-ls-files.txt---stage)。これは画像decodeや配布完結の保証ではない。

charset preflightで内容を無視する要素のうち、TITLE/STYLE/SCRIPTだけはhead状態を維持する。TEXTAREA/IFRAME/NOSCRIPT/XMPの開始後はheadを終了した状態にし、後続のmetaや再度のheadタグでcharset宣言を復活させない。[HTML4 Transitional DTDのhead内容](https://www.w3.org/TR/html401/sgml/loosedtd.html)に基づく限定診断で、完全なhead文法検証はSGMLの範囲として分ける。

過去監査のPR内commitは現在の履歴では祖先だが、将来のsquashとPR ref削除後の新規cloneで取得可能とは限らない。[選択した監査入力5版の逆差分](plans/legacy-historical-inputs-20261024.json)は、同じtree内の変更していない3HTMLから原bytesをメモリ内で再構成する。サイズ/SHA256/Git blobを前後で照合し、入力変更時は失敗する。再照合は上記unittestの`HistoricalAuditRegressions`に含まれ、旧commit objectの取得・新ref・ファイル書出しは不要。元のcommit ID・古いhash・当時の実証結果は履歴として保持する。逆差分は当時のcommit graph/署名の復元や診断/rollbackの再実行を意味せず、snapshot/画像/全履歴の保存でもない。

終了コード0は限定検査で新規回帰がないことだけを示す。既知の配布不足はINCOMPLETEで、この入口自体はSGML検証・実表示を実行しない。別途行った3ページのSGML DTD検証は[2026-10-24の限定記録](plans/legacy-html-followup-20261024.json)を参照し、実表示は未確認として残す。私有snapshotでの解決をGit配布成立へ流用しない。JS/TSがない範囲の型検査は対象外で、型PASSとはしない。

HTML4のSGML DTD検証はOpenSP 1.5.2公式Windows版のonsgmlsと同梱DLLをtask専用領域に配置し、W3C公式HTML4.decl・loose.dtd・HTML4.cat・HTMLlat1.ent/HTMLsymbol.ent/HTMLspecial.entをローカル入力にして実施した。OS全体へのinstall・PATH・恒久環境変数の変更はしていない。出典・取得物hash・実入力hash・結果は[限定記録](plans/legacy-html-followup-20261024.json)に固定する。未確認の別配布バイナリで置き換えない。

再実行が必要な変更時は、隔離した対象HTMLの宣言charsetを厳格に確認する。今回のUTF-8入力では子プロセス内だけ`SP_CHARSET_FIXED=YES`、`SP_ENCODING=utf-8`と明示したローカルcatalog/search pathを使い、絶対pathの `onsgmls -s -c <local-HTML4.cat> <HTML4.decl> <local-document>` を実行した。catalogは`OVERRIDE YES`とTransitional/3種のentityのローカル対応を使う。今回取得していないStrict/Frameset文書へ検証範囲を広げない。日本語の正常入力と、不正属性・不正構造を拒否する合成入力で入口を確認済み。成功済み入力を理由なく反復しない。

変更後の既存3ページは終了コード0・診断なし。ただしDTDが表せない値制約、完全CSS規則、リンク先の実在、アクセシビリティ全体、スマホ表示・runtimeは別途確認する。これは全サイトやHTML4仕様全文への適合宣言ではない。公開validatorへの本文送信やHTML5/XMLへの代替変換は行わない。[公式Windows配布](https://sourceforge.net/projects/openjade/files/opensp/1.5.2/)、[OpenSP](https://openjade.sourceforge.net/doc/nsgmls.htm)、[入力encoding](https://openjade.sourceforge.net/doc/charset.htm)、[HTML4の検証とcatalogおよび限界](https://www.w3.org/TR/html401/sgml/intro.html)。

## 3. 通常Git保存と公開判断を分ける

```text
git status --short --branch
git diff --check
```

確認した対象だけを既存の同名feature branchに保存し、限定検査・独立レビュー・通常push・remote読戻しを行う。[送信先確認](legacy-publication.md#通常の-git-保存と送信先確認)を守る。Astro buildやgit pushだけで公開可能とはしない。旧Cloudflare自動公開の記述は現行操作の根拠にしない。

このホームページの最終置換は、整理・規格/配布参照・実表示・復元/rollbackが揃った後という条件付き。現時点は本番削除/公開・master変更を行わず、実行時の正確な対象と許可を別に確認する。全削除を先行しない。

---

## 4. さくらの旧手作業記録（現行接続コマンドではない）

### 4-0. 共通ルール（毎回・厳守）

| 項目 | 値 |
|---|---|
| プロトコル | **SFTPのみ**（`ftp://` はタイムアウトで不可） |
| ホスト | `ippon.sakura.ne.jp` |
| ユーザー | `ippon` |
| パスワード | 手順書には書かない（メモリ `reference-sakura-sftp` に保管） |
| 公開される場所 | `/home/ippon/www/` 配下**のみ**（`/home/ippon/kaihou_ippon/` 等は配信されない） |
| 文字コード | **ファイルごとに異なる（混在）**。下表参照。「Shift_JIS固定」ではない |

**文字コードはファイルごとに違う（2026-06-18 訂正）— 思い込みで上げない:**
| ファイル | 文字コード |
|---|---|
| `index.htm`（TOP） | **Shift_JIS** |
| `kaihou_ippon/backnumber/ipponNNg.html`（会報） | **Shift_JIS** |
| `gyouji_yotei/YYYYgyouziyotei.html`（行事予定, Homepage Builder v19） | **UTF-8** |
| その他 | **取得して実エンコーディングと `<meta charset>` を必ず確認**し、それに合わせる |

- 既存ファイルを**まず取得 → ローカルで編集 → 上書きアップ**する（テンプレ踏襲）。新規はゼロから作らず**前年版をコピー**して中身差し替え。
- 取得は `--compressed` を付ける（gzipで来るため。付けないと中身がgzipバイナリになる）。
- エンコーディング判定：取得後 Python で `data.decode('utf-8')` の成否で UTF-8 / Shift_JIS を見分ける。`<meta charset>` 表記とも一致させる。
- **元ファイルと同じ文字コードで保存してアップ**（UTF-8ページをShift_JISで上げると化ける、逆も同じ）。
- アップロード：
  ```bash
  curl -T "<ローカルファイル>" \
    "sftp://ippon.sakura.ne.jp/home/ippon/www/<アップ先パス>" \
    --user "ippon:<パスワード>" --insecure -v
  ```
- 取得して確認：`curl -s "sftp://.../home/ippon/www/<パス>" --user "ippon:<パスワード>" --insecure`

### 旧サイトのファイル地図（実測 2026-06-18）

| 種類 | 場所 |
|---|---|
| TOP / お知らせ | `www/index.htm` |
| 行事予定 | `www/gyouji_yotei/YYYYgyouziyotei.html` ※2025・2026は綴り **gyou_Zi_yotei**、〜2024は **gyou_Ji_yotei** |
| 保険・世話人のお願い | `www/gyouji_yotei/hoken_onegai YYYY.html` / `sewanin_onegai YYYY.html` |
| 例会報告 入口 | `www/reikai/houkoku_reikai.htm` |
| 例会報告 年度一覧 | `www/reikai/YYYYreikaihoukoku.html` ※**2017だけ綴りミス** `2017eikaihoukoku.html`（rが抜け） |
| 例会報告 個別 | `www/reikai/<個別>.html`（画像は年度フォルダ `www/reikai/YYYY/`） |
| 会報トップ | `www/kaihou_ippon/index_kaihou.htm` |
| 会報バックナンバー | `www/kaihou_ippon/backnumber/ipponNNg.html` ＋ 表紙 `SCANxxxxx.jpg` |
| 会員発信 | `www/kaiinhassin/kaiinhassin.html` |

### 4-A. 例会報告（旧サイト）

例会報告は **入口 → 年度一覧 → 個別** の3階層構造。
1. **個別報告HTMLを作成**：前回の個別HTML（例 `reikai/170621soukai.html`）を取得・コピーし、本文と写真を差し替える。写真は年度フォルダ `www/reikai/2026/` に置く。
2. **年度一覧に追記**：`www/reikai/2026reikaihoukoku.html` に新報告へのリンクを1行足す。
3. **新年度を始めるとき**：年度一覧ファイル `2026reikaihoukoku.html` を前年版から新規作成し、入口 `www/reikai/houkoku_reikai.htm` の一覧の先頭に
   ```html
   <a href="2026reikaihoukoku.html">■ 2026年度例会報告</a><br><br>
   ```
   を追加する。
4. **TOPのお知らせ追記**（→ 4-B）。
5. 上記すべてを Shift_JIS で各パスへアップ。

### 4-B. お知らせ（旧サイト）

`www/index.htm` の「■ **お知らせ＆更新情報**」内、`<font size="-1">` の下にある `・…` の行を編集する（古い行を消し、新しい行を足す）。例：
```html
・2026年度の行事予定を公開しました。<br>
・◯月◯日の観察会報告を更新しました。
```
Shift_JIS で `www/index.htm` を上書きアップ。

### 4-C. 行事予定（旧サイト）

1. 前年版 `gyouji_yotei/2025gyouziyotei.html` を取得・コピーして `2026gyouziyotei.html` を作成、日程を差し替える（**綴りは gyouZiyotei**）。
2. 必要なら `hoken_onegai 2026.html` / `sewanin_onegai 2026.html` も前年版から作る。
3. **TOPのリンク変更**：`www/index.htm` の行事予定リンクを新年度に変更。形式は**絶対URL**：
   ```html
   ■ <a href="http://ippon.sakura.ne.jp/gyouji_yotei/2026gyouziyotei.html">2026年度の行事予定</a>
   ```
4. アップ。**行事予定HTMLは UTF-8**（Homepage Builder v19）。一方リンクを直す `index.htm` は **Shift_JIS**。それぞれ元の文字コードで保存する。
   > ※2026年度版は **2026-06-18 にアップ済み・index.htm のリンクも更新済み**（worklog 参照）。

### 4-D. 会報いっぽん（旧サイト）

1. `kaihou_ippon/backnumber/ipponNNg.html` と表紙 `SCANxxxxx.jpg` を作成。
2. 会報トップ `kaihou_ippon/index_kaihou.htm` に新号へのリンクを追加。
3. Shift_JIS でアップ。
   > ※36号(SCAN00053)・37号(SCAN00054)は **2026-06-17 にローカル作成済み**。サーバへの最終アップは手作業で実施する。

### 4-E. 会員発信（旧サイト）

`kaiinhassin/kaiinhassin.html` を編集してアップ。

### 4-F. 新サイト ⇄ 旧サイト 対応表（両方更新する早見表）

| 更新 | 新サイト | 旧サイト |
|---|---|---|
| 例会報告 | `src/content/reikai/*.md` ＋ `public/reikai/YYYY/` | `reikai/個別.html` ＋ `YYYYreikaihoukoku.html`（＋入口） |
| お知らせ | `src/content/news/*.md` | `index.htm` のお知らせ欄 |
| 行事予定 | `src/pages/events.astro` | `gyouji_yotei/YYYYgyouziyotei.html` ＋ `index.htm` リンク |
| 会報 | `src/content/kaihou/*.md` | `backnumber/ipponNNg.html` ＋ `index_kaihou.htm` |
| 会員発信 | `src/content/kaiinhassin/*.md` | `kaiinhassin/kaiinhassin.html` |

---

## 5. つまずきポイント（事故防止メモ）

- **文字コード**：新サイトは UTF-8。**旧サイトはファイルごとに混在**（index.htm/会報=Shift_JIS、行事予定=UTF-8）。「Shift_JIS固定」と思い込まず、§4-0の表と実ファイルを確認し**元と同じ文字コード**で上げる。
- 新サイトの画像パスは先頭に `/`（`/reikai/2026/1.jpg`）。付け忘れると表示されない。
- 行事予定 (§1-C) だけ Markdown ではなく `events.astro` を直接編集。**年度見出しの直し忘れ注意**。
- 旧サイトの**綴りの罠**：行事予定 2025/2026 は `gyouZiyotei`（〜2024は `gyouJiyotei`）／例会報告 2017一覧は `2017eikaihoukoku.html`（rが抜け）。既存リンクに合わせる。
- 旧サイトは **SFTPのみ**。アップ先は必ず `/home/ippon/www/` 配下（他は配信されない）。
- 現行作業は§2の限定診断と残条件を確認し、§3の通常保存へ進む。Astroのnpm入口は再有効化しない。

---

## 6. メール・ドメインについて（2026-06-18 確認済みの補足）

- 会の連絡用メール（TOPに記載の `mashryum@poem.ocn.ne.jp`、栗原代表 `kurihara@qa2.so-net.ne.jp` ほか）は各自の**個人ISP**メールで、**さくら・Cloudflare のドメイン設定とは無関係**。サイトのドメインを変えてもメールは壊れない。
- 新サイトはまだ独自ドメイン未取得（`*.pages.dev` のまま）。独自ドメインを取得して Cloudflare に接続しても、メール用の独自ドメインは存在しないため MX（メール宛先）の事故は起きない構成。
