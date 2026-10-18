"""Apple メモの学習メモを memo/ に Markdown で取り込む（前回より後に更新されたものだけ）。

usage:
  python3 -I memo_import.py [--folder "Video learning"] [--memo-dir memo] [--since ISO8601] [--all] [--dry-run]

- 取り込み対象は指定フォルダとその配下のサブフォルダ（iCloud アカウント）。
- 「前回」は memo/ の各ファイルの modified の最大値。--since で上書き、--all で全件。
- 同じメモ（apple_note_id が同じ）のファイルがあれば、ファイル名（ID）はそのままで中身を更新する。
- 新しいメモは作成日を ID にする。同じ日のファイルがあれば -N を付けて既存の最大値＋1 にする。
- メモアプリ側で消したメモのファイルは消さない。
"""
import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path

JST = timezone(timedelta(hours=9))

# 1回の Apple Event でフォルダ内の全メモの属性をまとめて取り、本文は対象のメモだけ取る（1件ずつ問い合わせると非常に遅い）
JXA = r"""
function run(argv) {
  const target = argv[0], since = argv[1] ? new Date(argv[1]) : null;
  const Notes = Application("Notes");
  const acc = Notes.accounts.byName("iCloud");
  const folders = acc.folders();
  const names = folders.map(f => f.name());
  const parents = folders.map(f => { try { return f.container().name(); } catch (e) { return ""; } });
  const inTree = (i, depth) => {
    if (names[i] === target) return true;
    if (depth > 10) return false;
    const p = names.indexOf(parents[i]);
    return p >= 0 && p !== i && inTree(p, depth + 1);
  };
  const out = [];
  folders.forEach((f, i) => {
    if (!inTree(i, 0)) return;
    const ids = f.notes.id(), mods = f.notes.modificationDate();
    const created = f.notes.creationDate(), titles = f.notes.name();
    ids.forEach((id, k) => {
      if (since && mods[k] < since) return;
      const n = Notes.notes.byId(id);
      const locked = n.passwordProtected();
      out.push({folder: names[i], id: id, title: titles[k],
        created: created[k].toISOString(), modified: mods[k].toISOString(),
        locked: locked, body: locked ? "" : n.body()});
    });
  });
  return JSON.stringify(out);
}
"""


class NoteHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self.list_stack = []
        self.href = None
        self.in_table = False
        self.row = []
        self.cell = None
        self.rows = []

    def w(self, s):
        if self.cell is not None:
            self.cell.append(s)
        else:
            self.out.append(s)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("h1", "h2", "h3"):
            self.w("\n" + "#" * int(tag[1]) + " ")
        elif tag in ("b", "strong"):
            self.w("**")
        elif tag in ("i", "em"):
            self.w("*")
        elif tag in ("strike", "s", "del"):
            self.w("~~")
        elif tag == "br":
            self.w("<br>" if self.cell is not None else "\n")
        elif tag in ("ul", "ol"):
            self.list_stack.append([tag, 0])
        elif tag == "li":
            depth = max(len(self.list_stack) - 1, 0)
            kind = self.list_stack[-1] if self.list_stack else ["ul", 0]
            if kind[0] == "ol":
                kind[1] += 1
                mark = f"{kind[1]}. "
            else:
                mark = "- "
            self.w("\n" + "  " * depth + mark)
        elif tag == "a":
            self.href = a.get("href")
            self.w("[")
        elif tag == "img":
            self.w("[画像]")
        elif tag == "object":
            self.w("[添付]")
        elif tag == "table":
            self.in_table = True
            self.rows = []
        elif tag == "tr":
            self.row = []
        elif tag in ("td", "th"):
            self.cell = []

    def handle_endtag(self, tag):
        if tag in ("h1", "h2", "h3"):
            self.w("\n")
        elif tag in ("b", "strong"):
            self.w("**")
        elif tag in ("i", "em"):
            self.w("*")
        elif tag in ("strike", "s", "del"):
            self.w("~~")
        elif tag == "div":
            self.w("<br>" if self.cell is not None else "\n")
        elif tag in ("ul", "ol"):
            if self.list_stack:
                self.list_stack.pop()
            if not self.list_stack:
                self.w("\n")
        elif tag == "a":
            self.w(f"]({self.href})" if self.href else "]")
            self.href = None
        elif tag in ("td", "th"):
            text = "".join(self.cell).strip()
            text = re.sub(r"(<br>)+$", "", text).replace("|", "\\|")
            self.row.append(text)
            self.cell = None
        elif tag == "tr":
            self.rows.append(self.row)
        elif tag == "table":
            self.in_table = False
            if self.rows:
                n = max(len(r) for r in self.rows)
                lines = []
                for i, r in enumerate(self.rows):
                    r = r + [""] * (n - len(r))
                    lines.append("| " + " | ".join(r) + " |")
                    if i == 0:
                        lines.append("|" + "---|" * n)
                self.out.append("\n" + "\n".join(lines) + "\n")

    def handle_data(self, data):
        if self.in_table and self.cell is None:
            return
        self.w(data.replace(" ", " "))


def to_markdown(body):
    p = NoteHTML()
    p.feed(body)
    p.close()
    md = "".join(p.out)
    md = re.sub(r"\*\*(\s*)\*\*", r"\1", md)  # 空の太字
    md = re.sub(r"(?m)^\s*(\*\*|\*|~~)\s*$", "", md)  # 見出しを囲んで残った記号だけの行
    md = re.sub(r"(?m)^(\*\*|\*)(#+ )", r"\2", md)
    md = re.sub(r"[ \t]+\n", "\n", md)
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md.strip() + "\n"


def safe_name(title):
    t = re.sub(r'[\\/:*?"<>|\n\r\t]', " ", title)
    t = re.sub(r"\s+", " ", t).strip().rstrip(".")
    return t[:60].rstrip() or "無題"


def to_jst(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(JST)


def read_front(path):
    """frontmatter から id / modified / apple_note_id を読む。"""
    meta = {}
    with path.open(encoding="utf-8") as f:
        if f.readline().strip() != "---":
            return meta
        for line in f:
            if line.strip() == "---":
                break
            k, _, v = line.partition(":")
            v = v.strip()
            meta[k.strip()] = json.loads(v) if v.startswith('"') else v
    return meta


def render(n, note_id):
    if n["locked"]:
        body = "（ロックされたメモのため本文は取り込めませんでした）\n"
    else:
        body = to_markdown(n["body"])
    front = [
        "---",
        f'id: "{note_id}"',
        f'title: {json.dumps(n["title"].strip(), ensure_ascii=False)}',
        f'channel: {json.dumps(n["folder"].strip(), ensure_ascii=False)}',
        f'created: {to_jst(n["created"]).isoformat(timespec="minutes")}',
        f'modified: {to_jst(n["modified"]).isoformat(timespec="minutes")}',
        "source: apple-notes",
        f'apple_note_id: {json.dumps(n["id"])}',
        "---",
        "",
    ]
    return "\n".join(front) + body


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", default="Video learning")
    ap.add_argument("--memo-dir", default="memo")
    ap.add_argument("--since", help="この日時以降に更新されたメモを取り込む（ISO8601）")
    ap.add_argument("--all", action="store_true", help="日時で絞らず全件を対象にする")
    ap.add_argument("--dry-run", action="store_true", help="書き込まずに対象だけ表示する")
    args = ap.parse_args()

    memo_dir = Path(args.memo_dir)
    memo_dir.mkdir(parents=True, exist_ok=True)

    by_note = {}  # apple_note_id -> 既存ファイル
    day_max = defaultdict(int)  # YYYYMMDD -> 使用済みの最大番号（番号なしは 1）
    latest = None
    for p in memo_dir.glob("*.md"):
        meta = read_front(p)
        if meta.get("apple_note_id"):
            by_note[meta["apple_note_id"]] = p
        m = re.match(r"(\d{8})(?:-(\d+))?_", p.name)
        if m:
            day_max[m.group(1)] = max(day_max[m.group(1)], int(m.group(2) or 1))
        if meta.get("modified"):
            t = datetime.fromisoformat(meta["modified"])
            latest = t if latest is None or t > latest else latest

    since = None
    if not args.all:
        since = datetime.fromisoformat(args.since) if args.since else latest
    since_arg = since.astimezone(timezone.utc).isoformat() if since else ""
    print(f"対象フォルダ: {args.folder}（サブフォルダを含む）")
    print(f"基準日時: {since.astimezone(JST).isoformat(timespec='minutes') if since else '全件'}")

    res = subprocess.run(
        ["osascript", "-l", "JavaScript", "-e", JXA, args.folder, since_arg],
        capture_output=True, text=True, timeout=1800,
    )
    if res.returncode != 0:
        sys.exit("メモアプリから読み出せませんでした: " + res.stderr.strip())
    notes = json.loads(res.stdout or "[]")

    added, updated, unchanged = [], [], []
    for n in sorted(notes, key=lambda x: x["created"]):
        existing = by_note.get(n["id"])
        if existing:
            note_id = read_front(existing).get("id") or existing.name.split("_", 1)[0]
            path = existing
        else:
            day = to_jst(n["created"]).strftime("%Y%m%d")
            day_max[day] += 1
            note_id = day if day_max[day] == 1 else f"{day}-{day_max[day]}"
            path = memo_dir / f"{note_id}_{safe_name(n['title'])}.md"
            by_note[n["id"]] = path
        text = render(n, note_id)
        if existing and existing.read_text(encoding="utf-8") == text:
            unchanged.append(path.name)
            continue
        (updated if existing else added).append(path.name)
        if not args.dry_run:
            path.write_text(text, encoding="utf-8")

    label = "（dry-run: 書き込みなし）" if args.dry_run else ""
    print(f"追加 {len(added)} 件 / 更新 {len(updated)} 件 / 変更なし {len(unchanged)} 件{label}")
    for name in added:
        print("  + " + name)
    for name in updated:
        print("  ~ " + name)


if __name__ == "__main__":
    main()
