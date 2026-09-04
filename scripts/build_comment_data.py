#!/usr/bin/env python3
"""Build the inline comment data block used by index.html."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path


DEFAULT_CSV = Path(
    "/Users/moomin/Documents/ChatGPT/New project/outputs/"
    "who_made_him_cultivate_ch1_comments/谁让他修仙的第1章评论_作者视角打标.csv"
)

START = "  // GENERATED_COMMENT_DATA_START"
END = "  // GENERATED_COMMENT_DATA_END"

COL_ID = "评论/回复id"
COL_TARGET_ID = "段落ID"
COL_TARGET_TEXT = "评论对象"
COL_USER_GUID = "用户guid"
COL_PARENT_ID = "父级回复id"
COL_TOP_ID = "顶级评论id（回复的评论id，评论不用到)"
COL_LEVEL = "作者视角_评论层级"
COL_BODY = "作者视角_评论正文"
COL_RAW_BODY = "评论内容"
COL_FIXED_TAGS = "作者视角_固定标签"
COL_CONTENT_TAGS = "作者视角_内容标签"
COL_LIKES = "点赞数"
COL_CREATED = "创建时间"
COL_SORT = "自定义排序"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--index", type=Path, default=Path("index.html"))
    parser.add_argument("--update-index", action="store_true")
    return parser.parse_args()


def int_or(value: str | None, default: int = 0) -> int:
    try:
        return int(str(value or "").strip())
    except ValueError:
        return default


def parse_body(row: dict[str, str]) -> str:
    body = (row.get(COL_BODY) or "").strip()
    if body:
        return body
    raw = (row.get(COL_RAW_BODY) or "").strip()
    if not raw:
        return ""
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    if isinstance(parsed, list) and parsed:
        return str(parsed[0].get("context") or "").strip()
    return raw


def split_tags(value: str | None) -> list[str]:
    tags: list[str] = []
    for part in (value or "").replace("；", ";").split(";"):
        tag = part.strip()
        if tag and tag not in tags:
            tags.append(tag)
    return tags


def normalize_target_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def comment_from_row(row: dict[str, str], row_index: int, level: str) -> dict:
    target_id = int_or(row.get(COL_TARGET_ID), -999)
    user_guid = str(row.get(COL_USER_GUID) or "").strip()
    return {
        "id": str(row.get(COL_ID) or "").strip(),
        "targetId": target_id,
        "targetType": "chapter" if target_id == -1 else "paragraph",
        "targetText": normalize_target_text(row.get(COL_TARGET_TEXT)),
        "parentId": str(row.get(COL_PARENT_ID) or "0").strip() or "0",
        "topCommentId": str(row.get(COL_TOP_ID) or row.get(COL_ID) or "").strip(),
        "level": level,
        "userGuid": user_guid,
        "nickname": user_guid or "匿名书友",
        "avatarUrl": "",
        "userBadge": "",
        "body": parse_body(row),
        "fixedTags": split_tags(row.get(COL_FIXED_TAGS)),
        "contentTags": split_tags(row.get(COL_CONTENT_TAGS)),
        "likeCount": int_or(row.get(COL_LIKES), 0),
        "createdAt": str(row.get(COL_CREATED) or "").strip(),
        "sortValue": int_or(row.get(COL_SORT), -1),
        "rowIndex": row_index,
        "replies": [],
    }


def build_payload(csv_path: Path) -> dict:
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    main_by_id: dict[str, dict] = {}
    main_comments: list[dict] = []
    reply_rows: list[tuple[dict[str, str], int]] = []
    skipped_empty = 0

    for row_index, row in enumerate(rows):
        body = parse_body(row)
        if not body:
            skipped_empty += 1
            continue
        level_name = (row.get(COL_LEVEL) or "").strip()
        if level_name == "回复":
            reply_rows.append((row, row_index))
            continue
        comment = comment_from_row(row, row_index, "main")
        main_comments.append(comment)
        main_by_id[comment["id"]] = comment

    orphan_replies = 0
    for row, row_index in reply_rows:
        reply = comment_from_row(row, row_index, "reply")
        parent = main_by_id.get(reply["topCommentId"]) or main_by_id.get(reply["parentId"])
        if not parent:
            orphan_replies += 1
            continue
        parent["replies"].append(reply)

    fixed_counts: Counter[str] = Counter()
    content_counts: Counter[str] = Counter()
    for comment in main_comments:
        fixed_counts.update(comment["fixedTags"])
        content_counts.update(comment["contentTags"])

    fixed_order = [
        "好评",
        "差评",
        "建议",
        "疑问",
        "提及作者",
        "明确提及其他书籍/作者/其他领域的作品如游戏影视",
        "剧透",
        "捉虫",
        "精彩二创",
        "建议加精的精彩评论",
        "建议屏蔽或禁言的评论",
        "金句/名场面/高光",
    ]
    tags = [{"name": "全部", "count": len(main_comments), "kind": "all"}]
    for tag in fixed_order:
        if fixed_counts[tag]:
            tags.append({"name": tag, "count": fixed_counts[tag], "kind": "fixed"})
    for tag, count in content_counts.most_common():
        tags.append({"name": tag, "count": count, "kind": "content"})

    target_total_counts: Counter[str] = Counter()
    for comment in main_comments:
        target_total_counts[str(comment["targetId"])] += 1 + len(comment["replies"])

    segment_ids = {comment["targetId"] for comment in main_comments if comment["targetId"] >= 0}
    return {
        "source": {
            "fileName": csv_path.name,
            "rowCount": len(rows),
            "mainCount": len(main_comments),
            "replyCount": sum(len(comment["replies"]) for comment in main_comments),
            "orphanReplyCount": orphan_replies,
            "skippedEmptyCount": skipped_empty,
            "chapterTotalCount": target_total_counts.get("-1", 0),
            "paragraphTotalCount": sum(
                count for target_id, count in target_total_counts.items() if target_id != "-1"
            ),
            "paragraphTargetCount": len(segment_ids),
        },
        "targetTotalCounts": dict(sorted(target_total_counts.items(), key=lambda item: int(item[0]))),
        "tagCounts": tags,
        "comments": main_comments,
    }


def js_block(payload: dict) -> str:
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    text = text.replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    return f"{START}\n  var COMMENT_DATA = {text};\n{END}"


def update_index(index_path: Path, block: str) -> None:
    content = index_path.read_text(encoding="utf-8")
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)
    # 用 lambda 作为 replacement，避免 block 中的 "\\" 被 re 解释为转义
    next_content, count = pattern.subn(lambda _m: block, content)
    if count != 1:
        raise SystemExit("Could not find exactly one generated comment data block in index.html")
    index_path.write_text(next_content, encoding="utf-8")


def main() -> None:
    args = parse_args()
    payload = build_payload(args.csv)
    block = js_block(payload)
    if args.update_index:
        update_index(args.index, block)
    else:
        print(block)
    stats = payload["source"]
    print(
        "built comment data: "
        f"{stats['mainCount']} main, {stats['replyCount']} replies, "
        f"{stats['paragraphTargetCount']} paragraph targets, "
        f"{stats['orphanReplyCount']} orphan replies"
    )


if __name__ == "__main__":
    main()
