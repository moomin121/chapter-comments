#!/usr/bin/env python3
"""Build comment-data-ch4.json for 廓晋_涨水（中） (chapter 98934448787084401).

与 build_chapter3_data.py 同一数据口径：58 列合体 CSV（起点后台导出 49 列 +
作者视角打标 8 列，2026-10-12 v4 口径全量逐条打标），标签直接行内取。

本章数据情况（实测）：
- 源 txt：表4_廓晋_涨水（中）.txt，标题行在 ccid= 之前，ccid 之后每行一段（60 行）。
- segmentId 是本章级编号（1~63，与 ugc_level3_id 完全一致），非全书级。
- sid == -1（36 行，quote=章节标题）→ 章评
- sid == 0（30 行，全部无 quote）→ 章末"本章说"，归章评（ch2/ch3 同口径）
- sid == 13 / 20：quote 为"确实很得用。""刘乘点点头。"，是站点段落里的
  短对话行，txt 里完全缺失 → 未匹配（targetId = -(10000+sid)）
- 其余 sid：quote 与 txt 行 1:1 对应（62 个 sid 中 60 个 ≥0.85 命中），
  模糊匹配 + 行内切分由 ch3 同款五阶段流程驱动
- 保留 quote 引导的单字修正（对齐 ≥0.85 的 1:1 简体替换），无全局字符替换
"""

from __future__ import annotations

import argparse
import csv
import difflib
import json
import re
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path

from opencc import OpenCC

DEFAULT_CSV = Path(
    "/Users/moomin/Desktop/评论/outputs/34842126904292008/tagged_comments.csv"
)
DEFAULT_OUT = Path("comment-data-ch4.json")
CHAPTER_TXT = Path(
    "/Users/moomin/WorkBuddy/评论skill/outputs/chapters/表4_廓晋_涨水（中）.txt"
)

T2S = OpenCC("t2s")

FIXED_ORDER = [
    ("好评", "👍"), ("差评", "🍅"), ("建议", "💡"), ("疑问", "❓"),
    ("提及作者", "👈"),
    ("明确提及其他书籍/作者/其他领域的作品如游戏影视", "📚"),
    ("剧透", "🎬"), ("捉虫", "🐛"), ("精彩二创", "🍚"),
    ("建议加精的精彩评论", "⭐"), ("建议屏蔽或禁言的评论", "🚫"),
    ("金句/名场面/高光", "✨"),
]
FIXED_NAMES = {name for name, _ in FIXED_ORDER}

# 模糊匹配阈值：≥MATCH_MIN 视为命中；≥FIX_MIN 的对齐才用于引导错字修正
MATCH_MIN = 0.5
FIX_MIN = 0.85


def norm_text(value: str) -> str:
    """归一化：只保留汉字/字母/数字（去全部标点与空白）。
    quote_msg 的破折号/引号形态与正文不一致，必须删标点才能稳定匹配。"""
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", re.sub(r"\s+", "", value or ""))


def norm_with_map(value: str) -> tuple[str, list[int]]:
    """归一化并保留 norm 索引 → 原文索引 的映射（用于回原文字符位置改错字）。"""
    out: list[str] = []
    idx: list[int] = []
    for i, ch in enumerate(value):
        if re.match(r"[\w\u4e00-\u9fff]", ch):
            out.append(ch)
            idx.append(i)
    return "".join(out), idx


def load_raw_lines() -> list[str]:
    lines = CHAPTER_TXT.read_text(encoding="utf-8").split("\n")
    i = next(i for i, ln in enumerate(lines) if ln.strip().startswith("ccid="))
    # 表4 的章节标题（"《廓晋》 第4章 涨水（中）"）在 ccid= 之前，ccid 之后
    # 直接是正文；每行一个段落（60 行），不做标点合并——分段由 quote 匹配驱动
    rest = [ln.strip() for ln in lines[i + 1:]]
    while rest and not rest[0]:
        rest.pop(0)
    return [ln for ln in rest if ln]


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


def best_window(nq: str, norm_paras: list[str]) -> tuple[float, tuple[int, int] | None]:
    """归一化 quote 在 1~3 行滑动窗口里找最佳对齐。"""
    best = (0.0, None)
    L = len(norm_paras)
    for start in range(L):
        for span in (1, 2, 3):
            if start + span > L:
                break
            text = "".join(norm_paras[start:start + span])
            ratio = difflib.SequenceMatcher(None, nq, text, autojunk=False).ratio()
            score = ratio - 0.02 * (span - 1)
            if score > best[0]:
                best = (score, (start, span))
    return best


def check_monotonic(sid_to_pos: dict[int, int], stage: str) -> None:
    items = sorted(sid_to_pos.items())
    for k in range(len(items) - 1):
        if items[k][1] > items[k + 1][1]:
            raise SystemExit(f"{stage} 匹配非单调: sid{items[k]} -> sid{items[k+1]}")


def build_paragraphs(rows: list[dict]):
    """五阶段构建最终分段（与 ch3 同款，分段由 quote 匹配驱动）：

    1) 行级窗口匹配（检测跨行段）
    2) 用各 sid 段落起点（quote 是段落前缀，对齐起点=真实段界）算行内切分点
    3) 行切成碎片后重新窗口匹配
    4) 跨碎片段合并成组；未覆盖碎片自成一段
    5) quote 引导单字修正（对齐得分 ≥FIX_MIN 的 1:1 简体替换）
    """
    raw_lines = load_raw_lines()
    line_norm: list[str] = []
    line_map: list[list[int]] = []  # 行内 norm 索引 -> 原文索引
    for p in raw_lines:
        n, m = norm_with_map(p)
        line_norm.append(n)
        line_map.append(m)

    sid_quotes: dict[int, str] = {}
    for row in rows:
        sid = get_sid(row)
        if sid is not None and sid > 0:
            q = (row["quote_msg"] or "").strip()
            if q and (sid not in sid_quotes or len(q) > len(sid_quotes[sid])):
                sid_quotes[sid] = q
    sid_nq = {sid: norm_text(T2S.convert(q)) for sid, q in sid_quotes.items()}
    sid_nq = {sid: nq for sid, nq in sid_nq.items() if nq}

    # ---- 阶段 1：行级窗口匹配 ----
    matched1 = {}
    for sid, nq in sid_nq.items():
        score, span = best_window(nq, line_norm)
        if span and score >= MATCH_MIN:
            matched1[sid] = (score, span)
    check_monotonic({s: sp[0] for s, (_, sp) in matched1.items()}, "阶段1")

    # ---- 阶段 2：行内切分点（sid 段落起点落在行中间 → 真实段界） ----
    cuts: dict[int, list[int]] = defaultdict(list)
    for sid, (score, (start, span)) in matched1.items():
        nq = sid_nq[sid]
        wt = "".join(line_norm[start:start + span])
        sm = difflib.SequenceMatcher(None, nq, wt, autojunk=False)
        blocks = sm.get_matching_blocks()
        # 切分依据：quote（段落前缀）的首匹配块落在窗口中部且覆盖 quote 主体
        if (not blocks or blocks[0].size < max(8, int(0.6 * len(nq)))
                or blocks[0].b <= 0):
            continue
        b = blocks[0].b
        acc = 0
        for li in range(start, start + span):
            ln = len(line_norm[li])
            if b < acc + ln:
                raw_pos = line_map[li][b - acc]
                # 段首的开引号等前导标点归属新段：切点左移吃掉开标点
                while raw_pos > 0 and raw_lines[li][raw_pos - 1] in "“‘（《【":
                    raw_pos -= 1
                if 0 < raw_pos < len(raw_lines[li]):
                    cuts[li].append(raw_pos)
                break
            acc += ln

    # ---- 阶段 3：切碎片 + 重新窗口匹配 ----
    frags: list[str] = []
    for li, p in enumerate(raw_lines):
        prev = 0
        for pt in sorted(set(cuts.get(li, []))) + [len(p)]:
            if pt > prev:
                frags.append(p[prev:pt])
            prev = pt
    frag_norm = [norm_text(t) for t in frags]

    matched2 = {}
    for sid, nq in sid_nq.items():
        score, span = best_window(nq, frag_norm)
        if span and score >= MATCH_MIN:
            matched2[sid] = (score, span)
    check_monotonic({s: sp[0] for s, (_, sp) in matched2.items()}, "阶段3")

    # ---- 阶段 4：合并跨碎片段；未覆盖碎片自成一段 ----
    frag_group: list[int | None] = [None] * len(frags)
    groups: list[list[int]] = []  # [start_frag, end_frag]
    for sid in sorted(matched2):
        fs, fspan = matched2[sid][1]
        fe = fs + fspan - 1
        if groups and fs <= groups[-1][1]:
            groups[-1][1] = max(groups[-1][1], fe)
        else:
            groups.append([fs, fe])
        gid = len(groups) - 1
        for k in range(fs, fe + 1):
            frag_group[k] = gid

    paragraphs: list[str] = []
    frag_para: list[int | None] = [None] * len(frags)
    group_para: dict[int, int] = {}
    i = 0
    while i < len(frags):
        gid = frag_group[i]
        if gid is None:
            frag_para[i] = len(paragraphs)
            paragraphs.append(frags[i])
            i += 1
        else:
            group_para[gid] = len(paragraphs)
            j = i
            while j < len(frags) and frag_group[j] == gid:
                frag_para[j] = len(paragraphs)
                j += 1
            paragraphs.append("".join(frags[i:j]))
            i = j

    sid_to_idx = {}
    for sid, (score, (fs, _)) in matched2.items():
        sid_to_idx[sid] = frag_para[fs]
    check_monotonic(sid_to_idx, "阶段4")

    # ---- 阶段 5：quote 引导单字修正 ----
    fixes: list[tuple[int, str, str, str]] = []
    for sid, para_idx in sorted(sid_to_idx.items()):
        nq = sid_nq[sid]
        para = paragraphs[para_idx]
        np_, idx_map = norm_with_map(para)
        sm = difflib.SequenceMatcher(None, nq, np_, autojunk=False)
        if sm.ratio() < FIX_MIN:
            continue
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "replace" and (i2 - i1) == 1 and (j2 - j1) == 1:
                old, new = np_[j1], nq[i1]
                # 只采纳简体对简体的替换（防繁体/噪声污染）
                if old != new and T2S.convert(new) == new and T2S.convert(old) == old:
                    fixes.append((para_idx, old, new, para[max(0, idx_map[j1]-6):idx_map[j1]+7]))
                    para = para[:idx_map[j1]] + new + para[idx_map[j1]+1:]
        paragraphs[para_idx] = para

    return paragraphs, sid_to_idx, fixes


def build_payload(csv_path: Path) -> dict:
    rows = list(csv.DictReader(open(csv_path, encoding="utf-8-sig")))
    paras, sid_to_idx, fixes = build_paragraphs(rows)

    print(f"段落构建: {len(paras)} 段（合并跨行段后），错字修正 {len(fixes)} 处:")
    for pidx, old, new, ctx in fixes:
        print(f"  段{pidx}: {old}->{new}  …{ctx}…")

    unmatched_sids = sorted(
        {get_sid(r) for r in rows
         if (s := get_sid(r)) is not None and s > 0 and s not in sid_to_idx}
    )
    print(f"未匹配 sid: {unmatched_sids}")

    def target_of(row) -> int:
        sid = get_sid(row)
        # 章评两入口：sid=-1（标题节点，quote=章节标题）与 sid=0（章末"本章说"，
        # 无 quote，内容为催更/剧情讨论）——与 ch1 "段落ID=0 视为章评"同口径
        if sid in (-1, 0):
            return -1
        if sid is not None and sid > 0:
            return sid_to_idx.get(sid, -(10000 + sid))
        if sid is None:
            return -9999
        return -(10000 + sid)  # 混入的其他章评论

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
        fixed = split_tags(row.get("作者视角_固定标签"))
        content = split_tags(row.get("作者视角_内容标签"))
        # 2026-10 v4 打标口径会把部分固定标签名（建议/捉虫/好评/疑问）也写进
        # 内容标签列：同名提升进 fixedTags，避免 tagCounts 出现重名胶囊、
        # 单条评论标签重复；筛选按 commentTags() 合并匹配，口径不变
        fixed_set = set(fixed)
        for t in content:
            if t in FIXED_NAMES and t not in fixed_set:
                fixed.append(t)
                fixed_set.add(t)
        content = [t for t in content if t not in FIXED_NAMES]
        if fixed or content:
            tag_hit += 1
        _tid = target_of(row)
        _quote = (row["quote_msg"] or "").strip()
        comment = {
            # 楼中楼挂靠必须用 ugc_id（parent_reply_id/top_reply_id 引用它）
            "id": str(row["ugc_id"]).strip(),
            "targetId": _tid,
            "targetType": "chapter",
            "targetText": (re.sub(r"\s+", " ", _quote)[:40] if _tid < -1 else ""),
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
            "ipLocation": get_ip(row),
            "likeCount": int(row["like_count"] or 0),
            "createdAt": str(row["create_time"] or "").strip(),
            "sortValue": -1,
            "rowIndex": idx,
            "replies": [],
        }
        if row["parent_reply_id"] not in ("", "0"):
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
        "paragraphs": paras,
        "targetTotalCounts": dict(sorted(target_counts.items(), key=lambda kv: int(kv[0]))),
        "tagCounts": tags_out,
        "comments": mains,
    }


def compact_payload(payload: dict) -> dict:
    data = deepcopy(payload)
    data.pop("paragraphs", None)  # 段落嵌 index.html，不入评论 JSON

    def compact_comment(comment: dict) -> None:
        for key in (
            "id", "targetType", "parentId", "topCommentId",
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
    parser.add_argument("--dump-paragraphs", type=Path,
                        help="把最终分段写成 JSON（供嵌入 index.html）")
    args = parser.parse_args()

    payload = build_payload(args.csv)
    if args.dump_paragraphs:
        args.dump_paragraphs.write_text(
            json.dumps(payload["paragraphs"], ensure_ascii=False, indent=0),
            encoding="utf-8",
        )
    text = json.dumps(compact_payload(payload), ensure_ascii=False, separators=(",", ":"))
    text = text.replace("</", "<\\/")
    if args.print_json:
        print(text)
    else:
        args.out.write_text(text, encoding="utf-8")
    stats = payload["source"]
    print(
        "built chapter4 comment data: "
        f"{stats['mainCount']} main, {stats['replyCount']} replies, "
        f"{stats['paragraphTargetCount']} paragraph targets, "
        f"{stats['chapterTotalCount']} chapter comments, "
        f"{stats['orphanReplyCount']} orphans, tag-matched {stats['tagMatchedCount']}"
    )


if __name__ == "__main__":
    main()
