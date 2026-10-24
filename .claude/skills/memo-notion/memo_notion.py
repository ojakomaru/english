"""10_memo/ のメモのうち、Notion に送っていないもの・送ったあとに変わったものを選ぶ（Notion には触らない）。

usage:
  python3 -I memo_notion.py [--memo-dir 10_memo] [--state notion_sync.json] plan [--limit N] [--json]
  python3 -I memo_notion.py body [--for-notion] <メモID>
  python3 -I memo_notion.py record <メモID> <NotionページID>

- 対応表（notion_sync.json）はメモ ID → {page_id, modified, sha256, synced_at}。
- 対応表にない → 追加。ファイルのハッシュが対応表と違う → 更新（チャンネルの移動も拾うため、modified ではなくハッシュで比べる）。
- 対応表にだけある ID（メモアプリで消したメモ）は何もしない。Notion のページは消さない。
- frontmatter に id がないファイル、同じ id が複数あるファイルは対象にせず警告を出す。
"""
import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "memo-import"))
from memo_import import read_front  # noqa: E402

JST = timezone(timedelta(hours=9))


@dataclass
class Memo:
    id: str
    title: str
    channel: str
    created: str
    modified: str
    path: Path
    sha256: str


def load_memos(memo_dir):
    """メモ ID → Memo と、警告の一覧を返す。"""
    found, warnings = {}, []
    for p in sorted(memo_dir.rglob("*.md")):
        meta = read_front(p)
        note_id = meta.get("id")
        if not note_id:
            warnings.append(f"id がないので飛ばしました: {p.relative_to(memo_dir).as_posix()}")
            continue
        memo = Memo(
            id=note_id,
            title=meta.get("title", ""),
            channel=meta.get("channel", ""),
            created=meta.get("created", ""),
            modified=meta.get("modified", ""),
            path=p,
            sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
        )
        found.setdefault(note_id, []).append(memo)
    memos = {}
    for note_id, items in found.items():
        if len(items) > 1:
            names = "、".join(m.path.relative_to(memo_dir).as_posix() for m in items)
            warnings.append(f"同じ id {note_id} のファイルが複数あるので飛ばしました: {names}")
            continue
        memos[note_id] = items[0]
    return memos, warnings


def load_state(path):
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(path, state):
    text = json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True)
    path.write_text(text + "\n", encoding="utf-8")


def plan(memos, state, limit=None):
    """("add" | "update", Memo) を作成日の古い順に返す。"""
    targets = []
    for memo in sorted(memos.values(), key=lambda m: (m.created, m.id)):
        rec = state.get(memo.id)
        if rec is None:
            targets.append(("add", memo))
        elif rec.get("sha256") != memo.sha256:
            targets.append(("update", memo))
    return targets[:limit] if limit else targets


def body(memo):
    """frontmatter を除いた本文。"""
    text = memo.path.read_text(encoding="utf-8")
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end >= 0:
            text = text[end + 5:]
    return text.lstrip("\n")


def to_notion(text):
    """Notion の Markdown に合わせる。表の中の <br> は <br /> に、ほかのタグらしい文字は文字として残るよう \\< にする（コードブロックの中はそのまま）。"""
    out, in_code = [], False
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            in_code = not in_code
        elif not in_code:
            line = re.sub(r"<(?!br />)(?=[A-Za-z/])", r"\\<", line.replace("<br>", "<br />"))
        out.append(line)
    return "\n".join(out)


def record(state, memo, page_id, now):
    new = dict(state)
    new[memo.id] = {"page_id": page_id, "modified": memo.modified, "sha256": memo.sha256, "synced_at": now}
    return new


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--memo-dir", default="10_memo")
    ap.add_argument("--state", default="notion_sync.json")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_plan = sub.add_parser("plan", help="追加・更新の一覧を出す")
    p_plan.add_argument("--limit", type=int)
    p_plan.add_argument("--json", action="store_true")
    p_body = sub.add_parser("body", help="frontmatter を除いた本文を出す")
    p_body.add_argument("--for-notion", action="store_true", help="Notion の Markdown に合わせて出す")
    p_body.add_argument("id")
    p_rec = sub.add_parser("record", help="送ったメモを対応表に記録する")
    p_rec.add_argument("id")
    p_rec.add_argument("page_id")
    args = ap.parse_args()

    memo_dir, state_path = Path(args.memo_dir), Path(args.state)
    memos, warnings = load_memos(memo_dir)
    state = load_state(state_path)

    if args.cmd == "plan":
        targets = plan(memos, state, args.limit)
        if args.json:
            print(json.dumps([
                {"kind": k, "id": m.id, "title": m.title, "channel": m.channel, "created": m.created,
                 "modified": m.modified, "page_id": state.get(m.id, {}).get("page_id")}
                for k, m in targets
            ], ensure_ascii=False, indent=2))
        else:
            for k, m in targets:
                print(f"  {'+' if k == 'add' else '~'} {m.id} {m.title}（{m.channel}）")
            adds = sum(1 for k, _ in targets if k == "add")
            rest = len(plan(memos, state)) - len(targets)
            print(f"追加 {adds} 件 / 更新 {len(targets) - adds} 件" + (f"（ほかに {rest} 件が残っています）" if rest else ""))
        for w in warnings:
            print("警告: " + w, file=sys.stderr)
    elif args.cmd == "body":
        if args.id not in memos:
            sys.exit(f"メモ ID が見つかりません: {args.id}")
        text = body(memos[args.id])
        sys.stdout.write(to_notion(text) if args.for_notion else text)
    elif args.cmd == "record":
        if args.id not in memos:
            sys.exit(f"メモ ID が見つかりません: {args.id}（対応表は変えていません）")
        now = datetime.now(JST).isoformat(timespec="minutes")
        save_state(state_path, record(state, memos[args.id], args.page_id, now))
        print(f"記録しました: {args.id} → {args.page_id}")


if __name__ == "__main__":
    main()
