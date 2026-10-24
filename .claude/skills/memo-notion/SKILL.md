---
name: memo-notion
description: 10_memo/（Apple メモ「Video learning」の写し）のうち、Notion にまだ送っていないもの・送ったあとに変わったものを、Notion の DB「Video learning」に追加・更新する。「メモを Notion に送って」「Notion に反映して」と言われたとき、/memo-import のあとに使う。
argument-hint: "[--limit N]"
---

# /memo-notion

`10_memo/` のメモを、Notion の DB「Video learning」にメモ1件＝ページ1件で写す。差分の判定は `memo_notion.py`、Notion への書き込みは Claude が Notion のツールで行う。開発案は `80_develop/D002_メモのNotion連携/`。

- DB：https://app.notion.com/p/b4b1214674a14f108b8adfc29a9dbde4
- データソース（書き込み先）：`collection://a84a6771-96e0-4e9d-b68d-37336b4fd967`
- 対応表：`notion_sync.json`（メモ ID → page_id・modified・sha256・synced_at）

## 手順

1. 対象を確認する（書き込まない）。引数で `--limit N` が渡されたら付ける。
   ```bash
   python3 -I .claude/skills/memo-notion/memo_notion.py plan --json
   ```
   - 0件なら、そう伝えて終わる。Notion には触らない。
   - 警告（標準エラー）が出たら、そのまま見せる。
2. 追加（`+`）・更新（`~`）の一覧を、ID とタイトル・チャンネルのセットで見せ、**「Notion に送りますか」とチャットで聞く。OK が出るまで Notion のツールを呼ばない。** 件数が多ければ `--limit` で区切ることを提案する。
3. OK が出たら、1件ずつ次を行う。
   - 本文：`python3 -I .claude/skills/memo-notion/memo_notion.py body --for-notion <ID>`
   - 欄：`タイトル`＝title、`メモID`＝id、`チャンネル`＝channel、`date:作成日:start`＝created、`date:更新日:start`＝modified（どちらも `date:…:is_datetime` は 1）
   - **追加**：`notion-create-pages`（parent は `data_source_id` に上のデータソース）で欄と本文を書く → できたページの ID で記録する。
   - **更新**：`page_id` のページに、`notion-update-page` の `update_properties` で欄を、`replace_content` で本文を書く → 記録する。ページが見つからないエラーなら、作り直すかをマメさんに聞く（勝手に作り直さない）。
   - 記録：`python3 -I .claude/skills/memo-notion/memo_notion.py record <ID> <ページID>`（1件書けたらすぐ）。
   - 失敗したら記録せずに次へ進み、最後に失敗した一覧（ID・タイトル・エラー）を見せる。
   - 本文が長すぎて書けないときは、前半でページを作り、残りを `insert_content`（position は end）で足す。
4. `git diff -- notion_sync.json` を見せてからコミットする。メッセージは `chore: Notion に送ったメモを記録（追加 N 件・更新 M 件）`。push はしない。

## 決まりごと

- Notion のページは削除しない。メモアプリで消したメモのページも残す。
- **Notion のページの本文は直接編集しない**（次の更新で置き換わる）。気づきや訳の添削は `20_log/` に書く。
- `10_memo/` のファイルも直接編集しない（`/memo-import` で上書きされる）。
- 対応表 `notion_sync.json` を手で直さない。直すのは `record` だけ。
- 新しいチャンネル（メモアプリの新しいフォルダ）が出たら、DB の「チャンネル」の選択肢に足してよいかを先に聞く。
- 単語・表現（Wordbook の Words・Chunks）とのつなぎはまだしない（D002 の I001・I002 で保留）。
