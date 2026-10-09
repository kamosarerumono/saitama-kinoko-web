> 2026-10-09 12:48 JST再発の最新状態: **BLOCKED / 公開再開保留**。
> 読取診断成功後の公開もtimeout。kondo-06/07を追加し合計7枚は独立HTTP SHA256一致、
> 残り写真11枚と記事は404、年間一覧/TOPはbaseline不変。既存7backup・全21stageを照合。
> 8枚目送信前の親directory NLSTが8.002577秒で失敗。control TCP/TLS約0.08秒、
> 新規接続2本・転送開始0であり、30秒転送期限/600秒全体期限の超過ではない。
> データTLS停止と同じ計測形を実curlのloopback FTPSで再現したが本番原因は未確定。
> 候補修正は確認済み画像directoryを直接検査し、残14件工程のFTPS接続50→39へ削減。
> 直前対象出現/未知写真/一覧失敗の停止・backup・TLS検証を保持。timeout延長/再試行なし。
> 合成59＋実curl loopback3試験PASS、candidateの本番効果は未受入。再公開コマンドは再案内しない。
> private証拠はtask-11 `incident-20261009/recurrence-124855/incident-report.json` と
> `ftps-handoff/readbacks/20261009T035240Z.json`。以下は初回停止時点と10/8の履歴。

> 2026-10-09 最新状態: **BLOCKED / 写真5枚のみ送信済み、記事未公開**。本人実行は
> `FTPS_STOP_EXIT_28`で停止。独立HTTPでkondo-01〜05が期待SHA256一致、残り13枚と記事は404、
> 年間一覧/TOPはbaseline一致。6枚目の送信開始なし。認証は成立しておりパスワード誤りとは判定しない。
> 自動再送・削除・復元なし。失敗は次の送信前のdirectory LIST確認中だが、元receiptに詳細がなく
> 通信段階は未確定。本人の次の操作は `publish_gunma_once.py --diagnose-ftps` の読取診断のみ。
> 診断receipt確認後に再開する場合、既存一致5枚を再送せず残り16ファイルへ限定する。
> 秘密を出さない操作/数値timing記録と診断モードを追加し、合成52試験PASS。本番FTPSでの修正効果は未検証。
> 根拠はtask-11の `incident-20261009/incident-report.json` と
> `ftps-handoff/readbacks/20261009T030834Z.json`。以下の10/8記録は当時の履歴。

# GT030 群馬の森観察会記事の公開checkpoint（2026-10-08）

状態: **WAITING_OWNER_INPUT / 未公開**。原稿・18JPEGの準備と承認訂正は完了。
旧さくらの群馬個別記事と新Cloudflareの群馬記事はいずれもHTTP 404。
Git納品・build・ローカル表示成功を公開完了とは扱わない。

## 承認と訂正

本人は2026年9月13日群馬の森観察会の「開会の様子」「同定結果の講評」
「同定作業」の掲載と、「ドクカラカサタケ→オオシロカラカサタケ」の写真説明への
適用を承認した。新旧記事の写真説明・altを訂正済み。本文9段落・観察目録87行・
開催情報12項目は原稿を保持。表記ゆれ・疑問符・仮称や種名を独自補完していない。
原メール・原稿原本・提供者メールアドレス・認証情報はGitに含めない。

## 検証結果

- 前回準備の40ファイルを全パス・SHA256・byte数で再照合。
- 原稿原本1本＋原写真18枚のSHA256不変。掲載写真18枚の画素不変、私的metadata除去。
- 新旧本文と原稿96段落・開催情報24セルの欠落0。新旧の写真説明訂正を照合。
- 標準Astro build: 305ページ、成功。既存lockfileと同じ依存を隔離repoで使用。
- 既存WAM経由の127.0.0.1限定表示: 新旧×desktop/390px、各18画像、破損0、横はみ出し0、画像HTTP SHA256一致。
- 新HOME→一覧→群馬、旧TOP→入口→年間一覧→群馬の導線と年間一覧の小川リンク保持を確認。
- 群馬専用FTPS手順の合成transport検証40件成功。backup前の送信なし、想定外差分・TLS/認証失敗・別ownerで停止、既存一致対象の再送0、小川個別記事/写真保持。

## 既存公開原本と対象

2026-10-08のHTTPS読戻しで、TOPと年間一覧は小川の公開済み完成形にSHA256一致。
取得した公開原本から群馬のみの差分を再作成した。TOPは更新案内1行の差替、
年間一覧は群馬リンク1件の追加。小川個別記事・写真の再公開はしない。

公開対象は群馬18JPEG＋個別記事＋年間一覧＋TOPの**21ファイル**のみ。
`docs/plans/gunma2026/` の旧サイト成果物はそのための準備であり、直接上書きしない。
公開直前にFTPS原本とHTTPS原本が今回baselineまたは今回完成形に完全一致することを再確認する。
別の更新が入っていれば停止し、その更新を保持して差分を作り直す。

既存の小川公開は20ファイルの独立HTTP読戻しが成立している。
今回の群馬21ファイルのHTTP読戻しは期待完成形一致0件で、18写真と個別記事は404、
TOP/年間一覧は200の公開原本。新サイト群馬記事も404。FTPS login/uploadは今回0件。

## 次の一手

利用可能な承認済みFTPS接続は確認できず、前回パスワードは本人のhidden入力だけで未保存。
本人の通常端末で以下を1回実行し、非表示欄へ直接入力する。

```bash
python3 /home/ayumi/Documents/Codex/2026-10-08/task-11/ftps-handoff/publish_gunma_once.py --publish
```

同フォルダの `HOW_TO_RUN.txt` と `manifest.json` に全対象・停止条件を固定。
既存小川publisherとの共有排他、GT030のowner/session/process確認、
暗号化必須FTPS・証明書検証・原本差分/backup・送信後と全体のHTTPS読戻しを維持。
パスワードはchat/argv/env/fileへ入れず、認証容器を読まず、永続保存しない。
`runs/*/receipt.json` の `PUBLICATION_VERIFIED`・`verified_count:21` が公開成功条件。
独立したHTTP確認は同フォルダの `readback_gunma.py` で行う。

この本人実行結果が親担当へ戻ったら、実ページと21ファイルを独立に再読戻しし、
既存GT030の公開状態を更新する。Discord短報告は公開確認後に親担当が扱う。
今回Discord・メール送信、main/master merge、Cloudflare deploy、新規認証保存・権限拡大は行っていない。
新サイトの公開経路は既存PRの採用と別工程であり、FTPS公開成功へ混同しない。

ローカル証拠: task-11の `verification/content-verification.json`、`browser-receipt.json`、
`ftps-tests.log`、`owner-preflight.json`、`public-preflight.json`、`ftps-handoff/readbacks/`。
