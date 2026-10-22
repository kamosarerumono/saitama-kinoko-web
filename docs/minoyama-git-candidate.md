# 固定Git差分から美の山の送信なし候補を選ぶ

前提は[静的入力の責任分担と保存証拠](minoyama-static-preparation.md)。旧URLの正本基準は保存済み公開後HTMLであり、訂正前の `docs/plans/minoyama2026/261004_minoyama.html` やAstro Markdownを自動採用しない。公開済みの本文・画像・導線と既存27対象の制約を維持する。

## 今回接続した範囲

`scripts/legacy_git_candidate.py` は、指定repoの固定base/head commitを読み取り、`public/reikai/2026/261004_minoyama.html` だけを候補記事として選ぶ。作業treeやindexの内容を候補へ取り込まず、checkout・fetch・push・外部diff/textconvを実行しない。全Git子プロセスで `--no-lazy-fetch` を指定し、partial clone等の欠落objectも暗黙取得せず停止する。このoptionに非対応のGitでも停止し、別経路へ切り替えない。Gitの置換objectも使わない。削除・rename・symlink等のtype変更、画像24件と導線2件の変更は拒否する。既存の平置き画像パスの変更も同様に拒否する。

- 対象外の差分だけなら `NO_RELEVANT_CHANGE`、出力なし。旧HTML資料の編集だけでは旧URLの候補にしない。
- 記事をGitへ初めて追加する差分は、保存済み公開後stageのbytesと完全一致する場合だけ受け入れ、`NO_CHANGE`、出力なし。基準採用と本文編集を同じ差分で混ぜない。
- 既存記事の変更ではbase blobが公開後stageのhashと一致することが必須。既知の公開前hashへ戻すheadも拒否する。改行・文字コードを含むbyte一致であり、Gitでの自動改行変換を一致とみなさない。
- 本文編集候補は固定headのblobを使い、画像・導線はSHAに固定された保存baselineから候補用一時rootへ渡す。その後は既存の送信なし静的準備処理を使う。タグ・属性・style/script等の変更を拒否し、manifest SHA・完全receipt・レビュー参照を照合する。

出力manifestのレビュー参照にはbase/headと固定入力パスを結び付ける。CLI結果にも固定commitを返す。周辺の未追跡ファイル、Gmail原文、資格情報、Git内の未依頼記事を読み込まない。一時rootは準備終了時に解放し、原本・保存baseline・receipt・未commit作業を変更しない。

```text
python scripts/legacy_git_candidate.py --repo <repoのtop-level> --base <固定commit SHA> --head <固定commit SHA> --baseline-bundle <保存bundle> --baseline-manifest-sha <固定manifest SHA> --receipt-run <対応する保存run> --output <新規出力先> --review-reference <依頼と差分レビュー参照>
```

## 起動境界と未実施

今回、実記事を `public/` へ配置せず、保存済み実データから新しい公開候補も生成していない。検証には一時Git repoと架空の27対象だけを使用する。既存公開URLの再取得は行わず、前回の18,804 bytes・SHA一致を保存証拠として保持する。

workflowは変更しない。既存 `legacy-publish.yml` のpush条件は `master` かつ `legacy-publication/bundles/**` の変更であり、今回のscript・test・文書追加はその条件に入らない。新しい入口はActionsを起動せず、公開引数やCMDも持たない。出力の存在や `PREPARED_OFFLINE` は公開承認・公開成功ではなく、既存のGit採用・内容確認・本番条件を置き換えない。

実データのGit配置、通常Gitイベントからの自動起動接続、一般記事・全サイトへの拡張、Environment準備、実公開・Gmail受付/定時接続は未受入。公開を伴うworkflow接続はこの送信なし工程へ混ぜない。

## 欠落objectの合成検証

最初の欠落objectテストはfixture内の既存Git objectを削除する準備段階で `WinError 5` となり、暗黙fetch禁止の検証まで到達しなかった。その削除は再試行せず、属性・ACL変更や別経路削除も行わない。原因の確認範囲はこのfixture準備の拒否までであり、本番repoへのアクセス拒否とは扱わない。

mockだけの検証では実Gitの欠落object処理を確認できないため、hashだけを算出してblobを保存せず、隔離repoの `update-index --cacheinfo`、`write-tree --missing-ok`、`commit-tree` で最初から欠落blobを参照するcommitを作る。既存objectの削除には依存しない。架空のpromisor remoteは存在しないローカルURLに限定し、fixtureのtransportは `protocol.allow=never` とする。実Gitを呼ぶ直前に全呼出しの `--no-lazy-fetch` 等をassertし、安全条件が欠ける回帰ではGit自体を起動しない。

このfixtureでは実際の `cat-file -s` が非ゼロで停止し、Git traceに子プロセス起動がなく、objectと出力も存在しないことを確認した。別のmock検証は欠落object相当・非対応option相当の終了コードと起動失敗・timeoutで、1回だけの呼出しと再試行・代替経路なしを確認する。これは外部remoteとの実通信や旧版Git実機の検証ではない。

前工程の12成功は保存証拠として保持し、反復していない。今回変更した欠落object試験1件と追加の独立契約試験2件の計3件が成功した。既存static準備12件や元の全体suiteの新しい合計とは扱わない。

## 既存Windows全体失敗との比較

既存記録のpre-push試験の `NtCreateDirectoryObject (0xC0000022)` はshell起動側の拒否として保持する。今回のGit object読取りと隔離fixtureの成功は、そのshell試験全体の回復証拠ではない。同じ失敗条件を反復せず、既存の実repo hookを変更・無効化しない。

メール受付は `mail_intake.py` がPOSIXの `st_mode & 0o077` と0700/0600を私有保存の前提としている。WindowsではそのbitだけでACLの私有性を証明できないため、bit検査をskip・削除して受入にはしない。Windowsの同等な私有保存契約と検証を定義する別工程が必要であり、このGit候補接続ではDB・ACL・認証設定を変更しない。既存Windows全体失敗とCI未報告は未解消として残す。
