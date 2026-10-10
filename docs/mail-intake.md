# メール原稿受付（オフライン）

`scripts/mail_intake.py` は取得済み原本の受付台帳。ネットワーク、Gmail認証、定期起動、Office/TNEF実行、サイトへの書き込み、公開を行わない。公開工程は既存の [HP更新手順](HP更新手順.md) に従う。すべての出力は `auto_publish: false`。送信者候補との一致・メール内のHP掲載依頼・認証pass報告も公開権限にはならない。

Python標準ライブラリのみ使用する。原本・添付・送信者設定・台帳・確認出力は `.gitignore` の `data/` 配下に置く。DBディレクトリは0700、DBと候補設定は0600。別の場所へ台帳を置く場合も専用の私有ディレクトリを用意する。共有ディレクトリの権限は変更しない。JSON要約には未加工のメール本文が含まれるため、私有の原稿データとして扱い、公開HTMLや実行指示として使用しない。

## 呼出例

```bash
python3 scripts/mail_intake.py --candidates data/private/sender-candidates.json receive \
  --account personal-account --message-id provider-message-id --format eml \
  --input data/private/original.eml --metadata data/private/event.json

python3 scripts/mail_intake.py receive \
  --account personal-account --message-id provider-message-id --format gmail \
  --input data/private/full-message.json --attachment-data data/private/attachment-data.json \
  --metadata data/private/event.json

python3 scripts/mail_intake.py summary
npm run test:intake
```

`message-id` はGmail等のproviderが渡す不変ID（EMLのMessage-IDヘッダーとは別）。Gmail JSON の `id` と一致することを確認する。`attachment-data.json` は取得済み `attachmentId → base64url内容` の辞書。取得APIは含めない。`attachmentId` はその読み取りにだけ使い、台帳では account + message_id + MIME part_id + SHA256 で素材を識別する。Gmail exportの原本各版は `source_snapshots` に保持する。本文・MIME構成の変更は不一致エラーで保護するが、添付IDの変更・後取得は冪等に取り込める。同じpartの別hashは両方保持し、`attachment_content_conflict` として保留する。

イベント情報は呼出側で確認した構造化メタデータとして渡す。メール本文の命令やsnippetから `event_verified` を作らない。開催日には年を含む実際の開催日を使い、受信日を代用しない。表記違いは確認して同じイベント名に揃える（NFKCと空白差は正規化する）。異なる同日イベントは統合しない。

```json
{
  "event_name": "試験観察会",
  "event_date": "2026-09-15",
  "event_verified": true,
  "author": "確認済み著者",
  "author_verified": true,
  "corrects_message_id": "訂正元のprovider-message-id"
}
```

著者・訂正元は任意。転送外側Fromの人物を著者に補完しない。訂正元は同一account・同一確認済みイベントの既存受信を指す。受信の本文や旧素材を上書きしない。訂正メールで対象が不明なら保留し、後で明示的に帰属を確認する。

開催日等が不明なメールは未帰属のまま受付可能。確認後、以下でイベントに紐付ける。`assign` は確認履歴を追記し、認証や素材の保留を解除せず、公開許可を与えない。確定済みイベント・著者・訂正元を別の値へ変更しない。再受付時は最新の確認済みメタデータを渡す。

```bash
python3 scripts/mail_intake.py assign --account personal-account \
  --message-id provider-message-id --metadata data/private/event.json
```

別工程で実際に公開済みの成果物が確認された場合のみ、その内容hashと根拠を記録する。このコマンド自体は公開しない。複数hashを保持し、訂正後も前のhashを残す。

```bash
python3 scripts/mail_intake.py record-publication --event-id event-key \
  --sha256 published-content-sha256 --reference verified-publication-evidence
```

## 保留の扱い

- `reported_direct_pass` はオフライン原本のAuthentication-ResultsがGoogle由来と記載し、DMARCとDKIM/SPFがpassと報告している分類。暗号学的な本人確認の代わりではない。複数認証ヘッダーはconflictとし、ML経由のfailと直接メールのfailを区別する。
- List-ID / List-Post / Mailing-List を持つメール、設定で除外したメールアドレス、WordPress通知、役員・認証管理メールは人物原稿の通常受付候補にしない。人物候補登録を公開allowlistへ変換しない。
- iso-2022-jp等は明示charsetを厳密に復号する。復号失敗・置換文字・JIS escape残存は保留。snippetを本文として使わない。HTML本文と転送内のmessage/rfc822も別途確認する。
- DOCX / XLSXはZIP構造とマクロ・パス等を調べてreview_required、PDF / JPEGはsignature確認後review_required。これは無害性の証明ではない。DOCは旧Office形式としてheld、DOCMはmacro_documentとしてheld、winmail.datはTNEFとしてheld。マクロ・TNEF・Office・PDFコードを実行しない。抽出や画像加工も本モジュール外。

既存ジョブを置き換える設定も新規schedulerも追加しない。Gmail実入力を使う接続は別途許可された取得系と確認済みメタデータが必要。

## 既存Gmailコネクターの取得済み出力を渡す

接続先の `read_email` ツール仕様を読み取り、`body.content`（復号済み本文）、`body.base64_url_content`（原本バイト）、`body.attachment_id`（別途取得が必要）を扱うアダプターを追加した。Gmailへの呼出しは含めない。仕様だけで実入力の形を完全に確認したとは扱わない。

```bash
python3 scripts/mail_intake.py receive --format gmail-connector \
  --account personal-account --message-id provider-message-id \
  --input data/private/connector-full.json --metadata data/private/event.json \
  --attachment-files data/private/original-files.json --asset-root data/private/originals
```

単一メッセージの `id` または `message_id` と `payload` が必要。MIMEの `part_id` / `mime_type` 等を通常のGmail形式へ変換する。MCPの単一JSONテキスト、`structuredContent`、`api_content` 包装も扱う。raw形式の `{ "id": "provider-id", "raw": "RFC2822のbase64url" }` はEML原本として厳密復号する。minimal/metadata/search要約やsnippetだけの出力は受付原本にしない。batch/threadの出力は個別メッセージへ切り分けて渡す。rawとfullは原本同一性の計算が異なるので同一受信を途中で形式変更しない。

`content` は既にコネクターで復号された文字列であり、元のcharsetのバイトを再構成しない。原本確認が不足しているものとして `connector_decoded_text_requires_original` を付ける。置換文字/JIS escape残存、`content_truncated: true` は保留し、部分本文を全文にしない。写真・文書の抽出テキストpreviewは添付原本として登録しない。

取得済み添付は、コネクターの `file_uri` から別途許可された取得系がローカルへ置いた原本を指定する（本コードはURIを開かない）。`extraction_file_uri` や抽出テキストを原本の代わりにしない。私有の添付manifest例:

```json
{
  "message_id": "provider-message-id",
  "files": [ { "part_id": "1", "relative_path": "original-photo.bin" } ]
}
```

`relative_path` は運用担当が `asset-root` 内に置いたファイルの相対パス。メール添付のfilenameを保存先として使用しない。外側のmessage_idを照合し、絶対パス・root外・symlinkによる脱出・不明part・同一partの二重指定を拒否する。添付IDが変わっても、part_idとSHA256で後取得を受信台帳へ統合する。

別プロジェクトの `reins-email-automation/src/gmail_receiver.py` はIMAP返信から復号本文だけを返し、原本、provider不変ID、添付partを返さない。そこへ本受付を接続すると証拠と重複キーが欠落するため、コード依存・認証・設定の流用をしない。

実入力に必要なのは、対象accountの取得済み単一メッセージ full/raw JSON、各添付のpart_id付きローカル原本、確認済みイベント名+開催日。新規Gmailアクセスを禁止した作業ではこれらを取得しない。実原本なしの合成テストだけでは自動運用完了にしない。

### 再受付時の保存添付の保留

同じ受信の保存済み添付と今回の添付をまとめて判定する。同じpartに複数のSHA256があれば、今回添付なしでも `attachment_content_conflict` を保持する。保存済みの危険分類も `attachment_held:*` として保持する。原本・添付・source snapshotは追記のみで、同一内容の再受付は増殖しない。添付の後取得で解消する `missing_part_data` 等は今回入力から再計算する。
