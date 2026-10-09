> 2026-10-09 最新状態: **保存方式の本人承認反映済み。端末での保存入力待ち**。
> 固定ファイルの明示読込を現行入口へ有効化。default hidden入力・既存scope/安全処理は保持。
> `save_local_credential_once.py --save` は本人端末の非表示入力1回だけで、
> 固定パスへ本人所有0700/0600の新規保存。既存値を読まず入力前停止、O_EXCLでraceも上書きせず、
> symlink/unsafe権限/ownerを拒否。新規ファイルのみ読戻し照合、値/hashをログに出さない。
> 現行入口＋保存helperの136試験PASS。実保存先はmetadata-only READY、secret作成/読取/chmod0。
> userの次の操作はこの保存helper1回だけ。停止なら再実行せず非秘密receiptを返す。
> agent実FTPS/送信0、記事未公開、最新独立証拠7写真一致/残14件。PASS530/timeout28は未解決。
> Git/manifest stage/原本backup/logからの除外は合成保存→offline21公開で検証。
> OS/cloud全体backupの除外設定は変更/確認していないため本人側で実行前確認。
> 証拠はprivate task-11 `incident-20261009/credential-activation/activation-receipt.json`、
> `OWNER_SAVE_INSTRUCTIONS.md`。保存成功を認証/公開成功としない。以下は当時の履歴。

> 2026-10-09 当時の状態: **認証拒否で停止。保存認証は本人確認前の候補のみ**。
> 17:53 JSTの写真1枚診断は現行hash `d396fdad…19fab6` と一致。制御TLS完了、
> USER331→PASS530/curl67。RETR/STOR0、写真読取/送信0byte。前回timeout28とは別段階。
> 生応答文は保存しておらず、入力誤りやアカウント制限は断定しない。
> hidden入力/UTF-8/quote/backslash/STDINは群馬・小川の成功版と同じ。小川との全体期限差だけ。
> 13種類の合成値が実curl/隔離TLSで同一bytes到達、制御文字は通信前に拒否。
> 別の保存候補はGit外の固定1ファイルを明示optionだけで読み、本人所有0700/0600、
> symlink/hardlink/unsafe祖先/欠損/改行を拒否。env/dotenv探索・fallback・retry・自動chmodなし。
> 全111試験PASS。現行入口・manifest/payload・差分/backup/HTTP検証は不変。
> 保存先と平文継続利用・OS/cloud backup除外の本人確認まで保存/有効化/実認証はしない。
> 8/31通知は本サーバーのFTP用も対象という非秘密確認を反映。現在有効の証明ではない。
> 証拠はprivate task-11 `incident-20261009/local-credential-proposal/review-receipt.json` と
> `REVIEW_LOCAL_CREDENTIAL.md`。本人の次の操作は案の確認のみ。以下は当時の履歴。

> 2026-10-09 当時の本人入力: **既存写真1枚だけの読取診断。公開は再実行しない**。
> 13:57 JSTの本人実行は公開前のkondo-01取得で30秒timeout、追加送信0。
> 最新HTTPSでも7JPEG一致、残14件・記事404、年間一覧/TOP baseline不変。
> 既存publisherへ `--diagnose-one-photo` を追加。固定kondo-01のFTPS GET1回だけ、
> 一覧/他写真/HTML/HTTP/STOR/再試行なし。実行時script hash、SIZE等の動詞/応答code、
> 制御/データTLSの固定段階・方向と順序を安全に記録。パスワード/引数/応答本文/raw stderrは保存しない。
> 制御SIZE応答待ち、RETR150後のデータTLS待ち、双方の区別不能を分ける。
> 合成71＋実curl loopback6試験PASS、8/30/600秒と証明書検証を保持。
> script SHA256 `d396fdad3720c8186b56fa93678caa40b01039ce526f9d779a759cd37c19fab6`。
> 本人通常端末で `python3 /home/ayumi/Documents/Codex/2026-10-08/task-11/ftps-handoff/publish_gunma_once.py --diagnose-one-photo`
> を非表示入力で1回だけ実行し、diagnoses/<run>/receipt.jsonを親担当へ返す。
> SINGLE_PHOTO_FTPS_READ_VERIFIEDは1枚読取成功であり公開完了ではない。本番診断未実行。
> private証拠は `incident-20261009/single-photo-diagnostic/handoff-receipt.json` と2検証log。
> 以下の公開再開案内は当時の履歴で、現在の実行指示ではない。

> 2026-10-09 接続復帰後の最新再開点: **本人の非表示入力1回で修正版を手動確認可能**。
> 最新HTTPSでも群馬7JPEG一致、残り11JPEG＋記事/年間一覧/TOPの14件。公開完了は未確認。
> task-11の `publish_gunma_once.py --publish` は合成59＋実curl loopback3試験済み修正版
> （SHA256 `c7937e6225360bcd89372634920a8bb7c42cd749dcb7713404dc53e1c8d2bd78`）へ直接進む。
> 一致済み7枚を飛ばし、再取得した9原本backup/ナビ差分を検証後に残対象だけを送信する。
> 接続数50→39、安全な通信履歴を追加。8/30/600秒の期限・TLS検証・直前guardは保持。
> 本番timeoutの細かな機序とcandidateの効果は未確定だが、その点だけで無期限保留にしない。
> 今回は本人の手動1回で確認し、再停止なら新receiptを返して繰り返さない。
> 根拠はprivate `incident-20261009/recurrence-124855/resume-readiness-20261009.json`、
> `ftps-handoff/readbacks/20261009T044948Z.json`。以下の保留記録は当時の履歴。

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
