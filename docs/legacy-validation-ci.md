# PR12の送信なしGHA検証

`legacy-validate.yml` は同じrepoからmasterを対象にするPR12の通常PRイベントだけを受け付ける。push/dispatch/schedule/publicationイベントは持たず、既存の公開workflowを変更しない。workflowはJSON表記のYAMLで、標準ライブラリだけで構造も検査できる。

標準の `ubuntu-24.04` runnerを1job、最大5分使用し、PR head SHAを明示checkoutする。`contents: read`、checkoutの資格情報保存なし、Environment・Secret・公開jobなし。新しいrunnerや外部サービスを導入しない。GitHubの公開repo用標準runnerを使い、結果artifactは小さいJSON1個、保存1日に限定する。

`validate_legacy_ci.py` は実checkout HEADとの完全一致を検査し、静的準備12件、Git候補15件、内容不変の本番確認入口の合成11件の固定38件だけを実行する。架空の27対象と一時Git repoを使用し、実公開データ・保存原本・Gmail・DBは使わない。Python socket接続と子Gitの全transportを処理内だけで禁止し、欠落objectのlazy fetch禁止も維持する。OS・ACL・Git永続設定を変更しない。依存の追加取得や本番HTTPS/FTPS接続はしない。

artifactはsource/checkout SHA、scope、実行件数、成功失敗・skip件数、失敗test ID、guard名だけ。fixture本体・原文・環境変数・例外本文・traceback・publisherの保存証拠は含めない。suite欠落・件数変化・skipを成功扱いせず、固定HEAD不一致は停止する。artifact登録だけでは成功にせず、run/job完了、実checkout SHA、検証結果、artifact内容を照合する。

ローカルでは変更に必要な合成試験とharness/trigger境界の契約試験を行い、既存成功suiteの同条件反復をしない。以前のGHA合成27件成功は保存証拠として残し、今回の固定38件と区別する。新しいLinux runnerの結果を元の全体suiteの新しい合計にしない。既存Windows全体失敗・元GT030・実配置の未受入は残る。本番確認は別の手動workflowであり、このPR用合成jobからは起動しない。

このPRへの通常push後に生じた同じheadのrunを1回だけ確認し、追加dispatch/rerunや重複pushをしない。runが起動しない・拒否される場合は、trigger/ref/登録/受付/runner開始のどこまで確認できたかを報告し、設定変更や未検証mergeで開通させない。
