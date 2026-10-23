# 配布不足34pathの同梱判断案（2026-10-24、未採用）

対象は既存3ページの43参照に対応する34pathだけ。**素材の同梱可否は判断待ちで、今回は素材追加・本番反映をしていない。** 既存の共通開発HP担当/claim・branchを継続する。

[機械可読一覧](legacy-distribution-inclusion-20261024.json)に34件の正確なpath、原素材bytes/SHA256、参照元、文字コード、意図する本番URL path、個別判断待ちを保存した。ファイル名の連続空白・綴りは維持し、URL pathの空白は`%20`にした。基準は`1e6f35fdbd2cc5ff695334ed403c2d12a823318d`。

## 必要素材と今回の判断

| 区分 | 件数 | 必要素材・判断 |
|---|---:|---|
| 共通CSS | 1 | P01。#2の319 bytes原バイト候補。literal url()/@importは0。完全CSS構文/escape参照は未検証。公開Git同梱の判断待ち |
| TOP・報告一覧 | 2 | P02/P34。保存原HTMLはCP932。各ページから追加12/25pathを参照。全体ナビの掲載範囲を先に決める |
| 2019記事 | 8 | P03–P10。保存原HTMLはUTF-8。P10以外は追加の直接参照あり。日付の原稿確認は保留 |
| 2020記事 | 4 | P11–P14。保存原HTMLはUTF-8。全件に追加の直接参照あり |
| 川越写真 | 19 | P15–P33。#2のJPEG原バイト候補。公開Git再配布・写真掲載範囲・必要な埋込metadata確認が判断待ち。今回は画像pixels/EXIF未読 |

34pathの原素材は全件保存目録にある。合計7,485,936 bytes。HTML14/CSS1の15ファイルだけを既存隔離展開物から読み、サイズ/SHA256・厳格復号を照合した。写真19件は固定目録の照合だけで、新規読取り/再hashをしていない。バックアップ原本・展開物は変更していない。

## 公開範囲を分けて判断する

- **公開GitHub**: repoのvisibilityはpublicと確認。将来素材をbranchへpushすると、master mergeや本番反映より前でも原バイト・本文・写真・埋込metadataが取得可能になる。この一覧の保存は原素材の同梱許可を意味しない。
- **さくら本番**: JSONの`intended_site_url_path`は既存URLを維持する候補で、現在のHTTP到達性や今回の公開を表さない。本番への反映・復旧は別途未実行。川越見本HTML自体は引き続きdocs内の見本で、今回の34件に含めず、publicへの配置採用もしていない。
- **保存根拠**: 34件とも10/21公開収集範囲に対応する#2目録記録がある。過去の掲載記録は現在の公開Git再配布/掲載許可を代替しない。原写真の提供者・掲載/再配布範囲は未確定。alt/caption上の会長/副会長/同定風景等から人物・行事写真の可能性があり、写真自体の人物識別は今回していない。
- **同梱対象外**: ZIP、private snapshot、名前対応表、展開tree、原稿/Office、認証情報、追加55path。追加対象の正確な名前とedge表は私有資料へ保持し、この公開Git案へ転記していない。

## 34件だけでは配布完結と判断できない

HTML14件の一次URL属性は173参照（保存先に解決171、外部等2）。171の内訳は既存Git103・当初34内3・追加保存素材65参照/55path。追加55は画像22、CSS1、リンク先HTML32で、いずれも保存目録のhistorical public scope内。既存Git103は正確なpathが追跡済みという判定で、今回その原バイト・表示を再検証した意味ではない。

追加55の本文/画像/CSSは未読・未同梱。55件のさらに先は辿っておらず、サイト全体の不足総数ではない。CSSは選択15テキスト中のliteral url()/@import tokenを調べて0だっただけで、escape・動的参照・完全CSS文法・fragment・実表示の合格ではない。

- 見た目に直接必要な追加素材は画像22とCSS1。ナビ先として必要な追加HTMLは32。両者の公開範囲を分けて決める。
- P10は列挙した一次参照がすべて既存Git内。ただし再帰的配布・実表示は未確認。
- CSS1＋川越写真19だけを将来同梱した場合、当初43参照中20参照分のpath不足に対応する計算になる。残り23参照/14HTML、川越見本のpublic採用、実表示・本番受入は別途残る。これは未実行の数量比較である。

## 対象一覧

下表はすべて`public/`配下の配置候補。正確な連続空白とURL表記・hashはJSONを正とする。「追加」はそのHTMLからの一次参照先のうち当初34にもGitにも無いdistinct path数。素材の採用状態は全件「判断待ち」。

| ID | `public/`以下の候補path | 種類 | bytes | 追加 |
|---|---|---|---:|---:|
| P01 | `hpbsite.css` | CSS | 319 | 0 |
| P02 | `index.htm` | HTML | 3,951 | 12 |
| P03 | `reikai/2019/190519  soukai.html` | HTML | 13,539 | 2 |
| P04 | `reikai/2019/190623 kawagoe kansatukai.html` | HTML | 97,263 | 1 |
| P05 | `reikai/2019/190721 ogawagenkipuraza.html` | HTML | 132,243 | 1 |
| P06 | `reikai/2019/190825  minoyama kansatukai.html` | HTML | 147,623 | 1 |
| P07 | `reikai/2019/190917  gunmanomori kansatukai.html` | HTML | 13,969 | 3 |
| P08 | `reikai/2019/191006  minoyama kansatukai.html` | HTML | 22,031 | 1 |
| P09 | `reikai/2019/191215  kinokohapyoubenkyoukai.html` | HTML | 29,200 | 1 |
| P10 | `reikai/2019/200315  syokukin benkyoukai.html` | HTML | 51,036 | 0 |
| P11 | `reikai/2020/200802 ogawagenkipuraza.html` | HTML | 117,868 | 1 |
| P12 | `reikai/2020/200913  minoyama kansatukai.html` | HTML | 23,636 | 11 |
| P13 | `reikai/2020/201011  gunnmanomori kansatukai.html` | HTML | 21,146 | 1 |
| P14 | `reikai/2020/201103  akigasekouen kansatukai.html` | HTML | 14,901 | 5 |
| P15 | `reikai/2026/images_260628/akayamadori.jpg` | JPEG | 205,668 | — |
| P16 | `reikai/2026/images_260628/doutei_fuukei.jpg` | JPEG | 227,158 | — |
| P17 | `reikai/2026/images_260628/fukukaichou_kouhyou.jpg` | JPEG | 233,263 | — |
| P18 | `reikai/2026/images_260628/fukukaichou_setsumei.jpg` | JPEG | 245,468 | — |
| P19 | `reikai/2026/images_260628/hebikinokomodoki.jpg` | JPEG | 281,593 | — |
| P20 | `reikai/2026/images_260628/himekatashouro.jpg` | JPEG | 386,168 | — |
| P21 | `reikai/2026/images_260628/kagotake.jpg` | JPEG | 528,260 | — |
| P22 | `reikai/2026/images_260628/kaichou_aisatsu1.jpg` | JPEG | 275,393 | — |
| P23 | `reikai/2026/images_260628/kaichou_aisatsu2.jpg` | JPEG | 231,026 | — |
| P24 | `reikai/2026/images_260628/kaichou_kouhyou.jpg` | JPEG | 217,939 | — |
| P25 | `reikai/2026/images_260628/kareedatakemodoki.jpg` | JPEG | 337,845 | — |
| P26 | `reikai/2026/images_260628/kotengutakemodoki.jpg` | JPEG | 446,225 | — |
| P27 | `reikai/2026/images_260628/murasakiyamadoritake.jpg` | JPEG | 431,990 | — |
| P28 | `reikai/2026/images_260628/naratakemodoki.jpg` | JPEG | 474,083 | — |
| P29 | `reikai/2026/images_260628/satoyamatamagotake.jpg` | JPEG | 467,091 | — |
| P30 | `reikai/2026/images_260628/tsunomatatake.jpg` | JPEG | 371,515 | — |
| P31 | `reikai/2026/images_260628/uchiwatake.jpg` | JPEG | 466,505 | — |
| P32 | `reikai/2026/images_260628/yamadoritakemodoki.jpg` | JPEG | 462,970 | — |
| P33 | `reikai/2026/images_260628/zaraenoharatake.jpg` | JPEG | 504,291 | — |
| P34 | `reikai/houkoku_reikai.htm` | HTML | 2,760 | 25 |

## 残件と選べる範囲

判断を具体化する単位は、(A) P01と写真P15–P33の原バイト公開Git同梱、(B) 各HTMLと追加素材をどこまで含めるか、(C) 本番反映、の3つ。Aの承認をB/Cへ拡張しない。原バイトをそのまま公開できない素材は、変換や除去を自動実施せず、その対象を保留する。

次の作業は対象IDごとの公開Git同梱範囲と、追加55pathのうち必要な範囲を決めること。必要素材が確定後の限定検証・表示確認・従来の本番rollback条件は残る。今回、素材コピー、写真/本文/URLの変更、公開、復旧、master/認証/TLS/設定変更は0。

**原稿確認2件は保留継続**: 川越の「サトタマゴタケ／サトヤマタマゴタケ」と、2019年度一覧の「9月17日（日）」の実開催日。写真同定や日付の推測訂正はしない。
