# 英語学習

## 記録
- 学習記録は 20_log/YYYY/YYYYMMDD_英語学習.md に書く。同じ日の記録は同じファイルに追記する。
- 既存の記録は消さない。
- 新しく覚えた単語・表現は Notion の Wordbook（単語は Words、表現は Chunks）に書く。

## メモ（10_memo/）
- 10_memo/ は Apple メモ「Video learning」の写し。/memo-import で取り込む。
- 10_memo/ の下はメモアプリと同じフォルダ構成（チャンネル名のフォルダ）。
- 10_memo/ のファイルは直接編集しない（取り込みで上書きされる）。

## サジェスト
- progress.md の目標と、直近2週間の log を根拠にする。
- 何を根拠にしたか（どの日の記録か）を示す。
- 目標の到達状況が変わったら progress.md を更新する。

## 索引
| 知りたいこと | 見る場所 |
|---|---|
| 今の状況・次にやること | STATUS.md（下で読み込む） |
| 英語の目標と到達状況 | progress.md（STATUS.md とは別物） |
| 学習メモの写し | 10_memo/（取り込みは /memo-import） |
| メモの Notion への送り | /memo-notion、送った記録は notion_sync.json |
| メモの Notion 連携の要件・課題・決まったこと | 80_develop/D002_メモのNotion連携/ |
| 単語・表現 | Notion の Wordbook（Words・Chunks） |
| 済んだことの経緯 | git log |

## 気をつけること
- 10_memo/ は直接編集しない。気づきや訳の添削は 20_log/ に書く。
- メモを取り込んだら、/memo-notion で差分を Notion に送る。

## STATUS.md（マメさんが見るファイル）
@STATUS.md

- 書き方と上限（件数・文字数・行数）は ClaudeProjects/CLAUDE.md の「STATUS.md（全プロジェクト共通）」に従う。
- 詳しいことは課題一覧などの正本に書き、STATUS には結論だけを書く。

## アプリ開発（80_develop/）
- このフォルダを良くするためのアプリの開発案は `80_develop/D000_名前/` に置く。一覧は `80_develop/開発案一覧.md`。
- 開発の作業を始める前に、その開発案の 00_概要 → 10_要件 → 20_設計 → 30_課題一覧 を読む。決まったことは 50_決定記録 にある。
- 要件・設計を変えたら、その文書の変更履歴に書き、ほかの文書への影響を整理する。決めたことは 50_決定記録 に書く。
- 課題の正本は各開発案の 30_課題一覧。STATUS.md には上位だけを、ID を付けずに言葉で載せる。
- 新しい開発案は ClaudeProjects 直下の `docs/90_templates/develop/` の雛形から作る。ID（D000）は english・kakeibo・lessons・secretary の `80_develop/` を通した最大値＋1。
