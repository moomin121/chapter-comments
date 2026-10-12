#!/usr/bin/env python3
"""Build comment-data-ch2.json for 玄鉴仙族_相累 (chapter 98935976990136488).

v3：改用 58 列合体 CSV（起点后台导出 49 列 + 作者视角打标 8 列，
全量 2717 条逐条打标，2026-10-12 v4 口径），标签直接行内取，
具备 v1 数据源缺失的全部结构：
- extend1.segmentId + quote_msg（被评段落原文）→ 段落映射
  （segmentId 是全书级段落编号，差值不固定，必须靠 quote 匹配建立映射表）
- parent_reply_id / top_reply_id → 楼中楼回复结构
- like_count → 真实点赞（最高 1890）
- extend2.ipLoc → IP 属地
- 标签从 tagging-result.json records 按 (guid, 归一化正文) 回贴

已知映射事实（由 quote 匹配验证）：
- segmentId < 0（-1/-110）→ 章评
- segmentId 与正文段落 idx 一一对应，映射表运行时建立
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from copy import deepcopy
from pathlib import Path

DEFAULT_CSV = Path(
    "/Users/moomin/Desktop/评论/outputs/24488947201576304/tagged_comments.csv"
)
DEFAULT_OUT = Path("comment-data-ch2.json")

FIXED_ORDER = [
    ("好评", "👍"), ("差评", "🍅"), ("建议", "💡"), ("疑问", "❓"),
    ("提及作者", "👈"),
    ("明确提及其他书籍/作者/其他领域的作品如游戏影视", "📚"),
    ("剧透", "🎬"), ("捉虫", "🐛"), ("精彩二创", "🍚"),
    ("建议加精的精彩评论", "⭐"), ("建议屏蔽或禁言的评论", "🚫"),
    ("金句/名场面/高光", "✨"),
]


def norm_text(value: str) -> str:
    """归一化：去空白 + 中英引号统一为空（quote_msg 用中文引号，正文用英文引号）。"""
    s = re.sub(r"\s+", "", value or "")
    return s.translate(str.maketrans("", "", "“”\"‘’'「」『』【】"))


def load_paragraphs() -> list[str]:
    src = Path("/Users/moomin/WorkBuddy/评论skill/outputs/chapters/表1_玄鉴仙族_相累.txt")
    lines = src.read_text(encoding="utf-8").split("\n")
    i = next(i for i, ln in enumerate(lines) if ln.strip().startswith("ccid="))
    rest = [ln.strip() for ln in lines[i + 1:]]
    while rest and (not rest[0] or rest[0].startswith("第一千五百八十七章")):
        rest.pop(0)
    raw = [p.strip() for p in "\n".join(rest).split("\n\n") if p.strip()]
    end_punct = tuple("。！？”…；：）】」』”? ")
    merged: list[str] = []
    buf = ""
    for p in raw:
        buf = (buf + p) if buf else p
        if buf.endswith(end_punct):
            merged.append(buf)
            buf = ""
    if buf:
        merged.append(buf)
    return merged


def parse_content(value: str) -> str:
    try:
        arr = json.loads(value)
        if isinstance(arr, list) and arr:
            return str(arr[0].get("context") or "").replace("\\n", "\n").strip()
    except json.JSONDecodeError:
        pass
    return value.strip()


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


def build_payload(csv_path: Path) -> dict:
    rows = list(csv.DictReader(open(csv_path, encoding="utf-8-sig")))
    paras = load_paragraphs()
    norm_paras = [norm_text(p) for p in paras]
    para_by_text = {p: i for i, p in enumerate(norm_paras)}

    def get_sid(row) -> int | None:
        try:
            return json.loads(row["extend1"]).get("segmentId")
        except (json.JSONDecodeError, KeyError):
            return None

    def get_ip(row) -> str:
        try:
            return str(json.loads(row["extend2"]).get("ipLoc") or "").strip()
        except (json.JSONDecodeError, KeyError):
            return ""

    def match_paragraph(quote: str) -> int | None:
        q = norm_text(quote)
        if not q:
            return None
        if q in para_by_text:
            return para_by_text[q]
        head = q[:30]
        if not head:
            return None
        for i, p in enumerate(norm_paras):
            if p.startswith(head) or head in p:
                return i
        return None

    # 第一遍：用一级评论的 quote 建立 segmentId → 段落 idx 映射表
    sid_to_idx: dict[int, int] = {}
    for row in rows:
        sid = get_sid(row)
        if sid is None or sid < 0:
            continue
        idx = match_paragraph(row["quote_msg"])
        if idx is not None:
            sid_to_idx.setdefault(sid, idx)

    def target_of(row) -> int:
        sid = get_sid(row)
        if sid is None or sid < 0:
            return -1
        idx = sid_to_idx.get(sid)
        if idx is not None:
            return idx
        idx = match_paragraph(row["quote_msg"])
        return idx if idx is not None else -1

    # 第二遍：构建评论
    by_id: dict[str, dict] = {}
    mains: list[dict] = []
    reply_rows: list[tuple[dict, int]] = []
    fixed_counts: Counter[str] = Counter()
    content_counts: Counter[str] = Counter()
    tag_hit = 0

    for idx, row in enumerate(rows):
        body = parse_content(row.get("content") or row.get("safe_content") or "")
        if not body:
            continue
        guid = str(row["guid"] or "").strip()
        ip = get_ip(row)
        # 58 列合体 CSV：标签直接从行内打标列取（分号分隔）
        fixed = split_tags(row.get("作者视角_固定标签"))
        content = split_tags(row.get("作者视角_内容标签"))
        if fixed or content:
            tag_hit += 1
        comment = {
            # 注意：parent_reply_id/top_reply_id 引用的是 ugc_id（雪花长ID），
            # 不是内部自增 id 列 —— 楼中楼挂靠必须用 ugc_id 作键
            "id": str(row["ugc_id"]).strip(),
            "targetId": target_of(row),
            "targetType": "chapter",
            "targetText": "",
            "parentId": "0",
            "topCommentId": "",
            "level": "main",
            "userGuid": guid,
            "nickname": guid or "匿名书友",
            "avatarUrl": "",
            "userBadge": "",
            "body": body,
            "fixedTags": fixed,
            "contentTags": content,
            "ipLocation": ip,
            "likeCount": int(row["like_count"] or 0),
            "createdAt": str(row["create_time"] or "").strip(),
            "sortValue": -1,
            "rowIndex": idx,
            "replies": [],
        }
        if comment["parentId"] == "0" and row["parent_reply_id"] not in ("", "0"):
            comment["parentId"] = row["parent_reply_id"].strip()
            comment["topCommentId"] = row["top_reply_id"].strip()
            reply_rows.append((comment, idx))
        else:
            mains.append(comment)
            by_id[comment["id"]] = comment

    orphans = 0
    for reply, _ in reply_rows:
        parent = by_id.get(reply["topCommentId"]) or by_id.get(reply["parentId"])
        if not parent:
            orphans += 1
            continue
        reply["level"] = "reply"
        parent["replies"].append(reply)

    for comment in mains:
        fixed_counts.update(comment["fixedTags"])
        content_counts.update(comment["contentTags"])

    tags_out = [{"name": "全部", "count": len(mains), "kind": "all", "emoji": ""}]
    for name, emoji in FIXED_ORDER:
        if fixed_counts[name]:
            tags_out.append({"name": name, "count": fixed_counts[name], "kind": "fixed", "emoji": emoji})
    for tag, count in content_counts.most_common():
        tags_out.append({"name": tag, "count": count, "kind": "content", "emoji": ""})

    target_counts: Counter[str] = Counter()
    for comment in mains:
        target_counts[str(comment["targetId"])] += 1 + len(comment["replies"])

    chapter_total = target_counts.get("-1", 0)
    paragraph_total = sum(c for t, c in target_counts.items() if t != "-1")
    return {
        "source": {
            "fileName": csv_path.name,
            "rowCount": len(rows),
            "mainCount": len(mains),
            "replyCount": sum(len(c["replies"]) for c in mains),
            "orphanReplyCount": orphans,
            "chapterTotalCount": chapter_total,
            "paragraphTotalCount": paragraph_total,
            "paragraphTargetCount": len({t for t in target_counts if t != "-1"}),
            "tagMatchedCount": tag_hit,
        },
        "targetTotalCounts": dict(sorted(target_counts.items(), key=lambda kv: int(kv[0]))),
        "tagCounts": tags_out,
        "comments": mains,
    }


def compact_payload(payload: dict) -> dict:
    data = deepcopy(payload)

    def compact_comment(comment: dict) -> None:
        for key in (
            "id", "targetText", "targetType", "parentId", "topCommentId",
            "level", "nickname", "avatarUrl", "userBadge",
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
        if not comment.get("ipLocation"):
            comment.pop("ipLocation", None)
        for reply in comment.get("replies") or []:
            compact_comment(reply)
        if not comment.get("replies"):
            comment.pop("replies", None)

    for comment in data["comments"]:
        compact_comment(comment)
    return data


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--print-json", action="store_true")
    args = parser.parse_args()

    payload = build_payload(args.csv)
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
        f"{stats['chapterTotalCount']} chapter comments, "
        f"{stats['orphanReplyCount']} orphans, tag-matched {stats['tagMatchedCount']}"
    )


if __name__ == "__main__":
    main()
