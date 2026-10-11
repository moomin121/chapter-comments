#!/usr/bin/env python3
"""Build comment-data-ch2.json for 玄鉴仙族_相累 (chapter 98935976990136488).

源数据特点（与第1章不同）：
- tagging-result.json records = 1288 条去重评论（源 1604 行按 用户+正文 合并）
- 无段落 ID → 全部按章评处理（targetId = -1）
- 无父级回复 ID → 全部为一级评论，无楼中楼
- 无点赞数 → likeCount 一律 0（前端渲染为零赞仅图标）
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from copy import deepcopy
from pathlib import Path

DEFAULT_SOURCE = Path(
    "/Users/moomin/WorkBuddy/评论skill/outputs/98935976990136488/tagging-result.json"
)
DEFAULT_OUT = Path("comment-data-ch2.json")

START = "  // GENERATED_COMMENT_DATA_START"
END = "  // GENERATED_COMMENT_DATA_END"

# 与 build_comment_data.py 保持同一套固定标签顺序与 emoji
FIXED_ORDER = [
    ("好评", "👍"),
    ("差评", "🍅"),
    ("建议", "💡"),
    ("疑问", "❓"),
    ("提及作者", "👈"),
    ("明确提及其他书籍/作者/其他领域的作品如游戏影视", "📚"),
    ("剧透", "🎬"),
    ("捉虫", "🐛"),
    ("精彩二创", "🍚"),
    ("建议加精的精彩评论", "⭐"),
    ("建议屏蔽或禁言的评论", "🚫"),
    ("金句/名场面/高光", "✨"),
]


def split_tags(value) -> list[str]:
    if isinstance(value, list):
        parts = value
    else:
        parts = str(value or "").replace("；", ";").split(";")
    tags: list[str] = []
    for tag in parts:
        tag = str(tag).strip()
        if tag and tag not in tags:
            tags.append(tag)
    return tags


def build_payload(source_path: Path) -> dict:
    data = json.loads(source_path.read_text(encoding="utf-8"))
    records = data["records"]

    comments: list[dict] = []
    fixed_counts: Counter[str] = Counter()
    content_counts: Counter[str] = Counter()

    for idx, rec in enumerate(records):
        ctx = rec.get("context") or {}
        body = str(rec.get("text") or "").strip()
        if not body:
            continue
        guid = str(ctx.get("commenter") or "").strip()
        comments.append(
            {
                "id": rec.get("id") or f"R{idx + 1:04d}",
                "targetId": -1,
                "targetType": "chapter",
                "targetText": "",
                "parentId": "0",
                "topCommentId": rec.get("id") or "",
                "level": "main",
                "userGuid": guid,
                "nickname": guid or "匿名书友",
                "avatarUrl": "",
                "userBadge": "",
                "body": body,
                "fixedTags": split_tags(rec.get("fixed_labels")),
                "contentTags": split_tags(rec.get("content_labels")),
                "likeCount": 0,
                "createdAt": str(ctx.get("comment_time") or "").strip(),
                "sortValue": -1,
                "rowIndex": idx,
                "replies": [],
            }
        )
        fixed_counts.update(comments[-1]["fixedTags"])
        content_counts.update(comments[-1]["contentTags"])

    tags = [{"name": "全部", "count": len(comments), "kind": "all", "emoji": ""}]
    for name, emoji in FIXED_ORDER:
        if fixed_counts[name]:
            tags.append({"name": name, "count": fixed_counts[name], "kind": "fixed", "emoji": emoji})
    for tag, count in content_counts.most_common():
        tags.append({"name": tag, "count": count, "kind": "content", "emoji": ""})

    total = len(comments)
    return {
        "source": {
            "fileName": source_path.name,
            "rowCount": total,
            "mainCount": total,
            "replyCount": 0,
            "orphanReplyCount": 0,
            "chapterTotalCount": total,
            "paragraphTotalCount": 0,
            "paragraphTargetCount": 0,
        },
        "targetTotalCounts": {"-1": total},
        "tagCounts": tags,
        "comments": comments,
    }


def compact_payload(payload: dict) -> dict:
    """与 build_comment_data.compact_payload 同口径：剥离 UI 可本地推导的字段。"""
    data = deepcopy(payload)

    def compact_comment(comment: dict) -> None:
        for key in (
            "id",
            "targetText",
            "targetType",
            "parentId",
            "topCommentId",
            "level",
            "nickname",
            "avatarUrl",
            "userBadge",
        ):
            comment.pop(key, None)
        if comment.get("sortValue") == -1:
            comment.pop("sortValue", None)
        if comment.get("likeCount") == 0:
            comment.pop("likeCount", None)
        if not comment.get("fixedTags"):
            comment.pop("fixedTags", None)
        if not comment.get("contentTags"):
            comment.pop("contentTags", None)
        for reply in comment.get("replies") or []:
            compact_comment(reply)
        if not comment.get("replies"):
            comment.pop("replies", None)

    for comment in data["comments"]:
        compact_comment(comment)
    return data


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--print-json", action="store_true")
    args = parser.parse_args()

    payload = build_payload(args.source)
    text = json.dumps(compact_payload(payload), ensure_ascii=False, separators=(",", ":"))
    text = text.replace("</", "<\\/")
    if args.print_json:
        print(text)
    else:
        args.out.write_text(text, encoding="utf-8")
    stats = payload["source"]
    print(
        "built chapter2 comment data: "
        f"{stats['mainCount']} main, {stats['replyCount']} replies, "
        f"{stats['paragraphTargetCount']} paragraph targets, "
        f"{stats['chapterTotalCount']} chapter comments"
    )


if __name__ == "__main__":
    main()
