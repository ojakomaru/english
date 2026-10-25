"""memo_notion.py のテスト。実行: python3 -m unittest discover -s .claude/skills/memo-notion -v"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import memo_notion as mn  # noqa: E402


def write_memo(d, name, note_id, title="タイトル", channel="Video learning",
               created="2026-08-09T15:39+09:00", modified="2026-08-09T19:17+09:00", body="本文の1行目\n"):
    p = Path(d) / name
    p.parent.mkdir(parents=True, exist_ok=True)
    front = ["---"]
    if note_id is not None:
        front.append(f'id: "{note_id}"')
    front += [
        f'title: "{title}"',
        f'channel: "{channel}"',
        f"created: {created}",
        f"modified: {modified}",
        "source: apple-notes",
        'apple_note_id: "x-coredata://test"',
        "---",
        "",
    ]
    p.write_text("\n".join(front) + body, encoding="utf-8")
    return p


class MemoNotionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / "10_memo"
        self.dir.mkdir()
        self.state_path = Path(self.tmp.name) / "notion_sync.json"

    def tearDown(self):
        self.tmp.cleanup()

    def memos(self):
        memos, _ = mn.load_memos(self.dir)
        return memos

    def test_new_memo_is_add(self):
        write_memo(self.dir, "20260809_a.md", "20260809")
        memos = self.memos()
        self.assertEqual(mn.plan(memos, {}), [("add", memos["20260809"])])

    def test_same_hash_is_skipped(self):
        write_memo(self.dir, "20260809_a.md", "20260809")
        memos = self.memos()
        state = mn.record({}, memos["20260809"], "page-1", "2026-10-24T09:00+09:00")
        self.assertEqual(mn.plan(self.memos(), state), [])

    def test_changed_content_is_update(self):
        p = write_memo(self.dir, "20260809_a.md", "20260809")
        state = mn.record({}, self.memos()["20260809"], "page-1", "2026-10-24T09:00+09:00")
        write_memo(self.dir, p.name, "20260809", modified="2026-10-01T10:00+09:00", body="直した本文\n")
        result = mn.plan(self.memos(), state)
        self.assertEqual([k for k, _ in result], ["update"])
        self.assertEqual(state[result[0][1].id]["page_id"], "page-1")

    def test_channel_change_is_update(self):
        write_memo(self.dir, "20260809_a.md", "20260809")
        state = mn.record({}, self.memos()["20260809"], "page-1", "2026-10-24T09:00+09:00")
        (self.dir / "20260809_a.md").unlink()
        write_memo(self.dir, "みさもさ/20260809_a.md", "20260809", channel="みさもさ")
        result = mn.plan(self.memos(), state)
        self.assertEqual([(k, m.channel) for k, m in result], [("update", "みさもさ")])

    def test_limit(self):
        write_memo(self.dir, "20260803_c.md", "20260803", created="2026-08-03T10:00+09:00")
        write_memo(self.dir, "20260801_a.md", "20260801", created="2026-08-01T10:00+09:00")
        write_memo(self.dir, "20260802_b.md", "20260802", created="2026-08-02T10:00+09:00")
        result = mn.plan(self.memos(), {}, limit=2)
        self.assertEqual([m.id for _, m in result], ["20260801", "20260802"])

    def test_body_strips_frontmatter(self):
        write_memo(self.dir, "20260809_a.md", "20260809", body="本文の1行目\n2行目\n")
        text = mn.body(self.memos()["20260809"])
        self.assertFalse(text.startswith("---"))
        self.assertEqual(text.splitlines()[0], "本文の1行目")

    def test_missing_id_is_warned(self):
        write_memo(self.dir, "x.md", None)
        memos, warnings = mn.load_memos(self.dir)
        self.assertEqual(memos, {})
        self.assertEqual(len(warnings), 1)

    def test_duplicate_id_is_excluded(self):
        write_memo(self.dir, "20260809_a.md", "20260809")
        write_memo(self.dir, "sub/20260809_b.md", "20260809")
        memos, warnings = mn.load_memos(self.dir)
        self.assertNotIn("20260809", memos)
        self.assertTrue(any("20260809" in w for w in warnings))

    def test_state_only_id_is_ignored(self):
        write_memo(self.dir, "20260809_a.md", "20260809")
        memos = self.memos()
        state = mn.record({}, memos["20260809"], "page-1", "2026-10-24T09:00+09:00")
        state["20250101"] = {"page_id": "page-old", "modified": "", "sha256": "", "synced_at": ""}
        self.assertEqual(mn.plan(memos, state), [])
        self.assertIn("20250101", state)

    def test_record_unknown_id_fails(self):
        write_memo(self.dir, "20260809_a.md", "20260809")
        res = subprocess.run(
            [sys.executable, "-I", str(HERE / "memo_notion.py"), "--memo-dir", str(self.dir),
             "--state", str(self.state_path), "record", "99999999", "xxx"],
            capture_output=True, text=True,
        )
        self.assertEqual(res.returncode, 1)
        self.assertFalse(self.state_path.exists())

    def test_to_notion_converts_br_and_escapes_tags(self):
        text = "| a<br>b |\n<div>x</div>\na < b\n```\n<keep>\n```\n"
        self.assertEqual(mn.to_notion(text), "| a<br />b |\n\\<div>x\\</div>\na < b\n```\n<keep>\n```\n")

    def test_body_cli_for_notion(self):
        write_memo(self.dir, "20260809_a.md", "20260809", body="| a<br>b |\n")
        res = subprocess.run(
            [sys.executable, "-I", str(HERE / "memo_notion.py"), "--memo-dir", str(self.dir),
             "--state", str(self.state_path), "body", "--for-notion", "20260809"],
            capture_output=True, text=True,
        )
        self.assertEqual(res.stdout, "| a<br />b |\n")

    def test_to_import_escapes_line_start_marks(self):
        text = "**閉じていない\nふつう **太字** です\n**閉じた太字**\n->矢印\n- 箇条書き\n"
        self.assertEqual(
            mn.to_import(text),
            "\\*\\*閉じていない\nふつう **太字** です\n**閉じた太字**\n\\->矢印\n- 箇条書き\n",
        )

    def test_line_start_number_and_initial_are_kept(self):
        text = "32. 歳の話\nM.\nM. Oh, yeah.\n2026.\n1.5 kg\nふつう 1. の文\n"
        expected = "32\\. 歳の話\nM\\.\nM\\. Oh, yeah.\n2026\\.\n1.5 kg\nふつう 1. の文\n"
        self.assertEqual(mn.to_import(text), expected)
        self.assertEqual(mn.to_notion(text), expected)

    def test_line_start_quote_is_kept(self):
        text = ">> Oh, yes.\n> 引用\n  >> 字下げ\n文の途中 >> はそのまま\n"
        expected = "\\>> Oh, yes.\n\\> 引用\n  \\>> 字下げ\n文の途中 >> はそのまま\n"
        self.assertEqual(mn.to_import(text), expected)
        self.assertEqual(mn.to_notion(text), expected)

    def test_quote_and_number_together(self):
        self.assertEqual(mn.to_import(">> 20. Oh, 13.\n"), "\\>> 20. Oh, 13.\n")

    def test_export_ids_rewrites_sent_memos(self):
        write_memo(self.dir, "20260801_a.md", "20260801", created="2026-08-01T10:00+09:00", body=">> a\n")
        write_memo(self.dir, "20260802_b.md", "20260802", created="2026-08-02T10:00+09:00")
        memos = self.memos()
        state = mn.record({}, memos["20260801"], "page-1", "2026-10-24T09:00+09:00")
        state = mn.record(state, memos["20260802"], "page-2", "2026-10-24T09:00+09:00")
        out = Path(self.tmp.name) / "out"
        written = mn.export(memos, state, out, ids=["20260801"])
        self.assertEqual([p.name for p in written], ["20260801.md"])
        self.assertEqual((out / "20260801.md").read_text(encoding="utf-8"), "\\>> a\n")

    def test_export_writes_only_adds(self):
        write_memo(self.dir, "20260801_a.md", "20260801", created="2026-08-01T10:00+09:00")
        write_memo(self.dir, "20260802_b.md", "20260802", created="2026-08-02T10:00+09:00", body="**閉じていない\n")
        memos = self.memos()
        state = mn.record({}, memos["20260801"], "page-1", "2026-10-24T09:00+09:00")
        out = Path(self.tmp.name) / "out"
        written = mn.export(memos, state, out)
        self.assertEqual([p.name for p in written], ["20260802.md"])
        self.assertEqual((out / "20260802.md").read_text(encoding="utf-8"), "\\*\\*閉じていない\n")

    def test_state_roundtrip(self):
        state = {"20260809": {"page_id": "p", "modified": "m", "sha256": "h", "synced_at": "日本語"}}
        mn.save_state(self.state_path, state)
        self.assertEqual(mn.load_state(self.state_path), state)
        self.assertIn("日本語", self.state_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
