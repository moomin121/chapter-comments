#!/usr/bin/env python3
"""Build comment-data-ch5.json for 剑烛大荒_小章居士 (chapter 35626462603382207 / ccid 98906955074040012).

与 ch3/ch4 同一数据口径：58 列合体 CSV（起点后台导出 49 列 +
作者视角打标 8 列，v4 口径全量逐条打标），标签直接行内取。

本章数据情况（实测，与 ch3/ch4 有三处不同）：
- 源 txt：表3_剑烛大荒_小章居士.txt，标题行在 ccid= 之前，正文 102 行。
- segmentId 为本章级编号（1~105），sid=-1（67 行，quote=章节标题）与
  sid=0（39 行，无 quote，章末"本章说"/催更）→ 章评，共 106。
- **坑 1：txt 混入 6 行起点广告位文字**（原行 22-27"冷艳女帝…"等），
  必须按精确文本剔除，否则广告会渲染成正文段落。
- **坑 2：站点分段比 txt 细/粗不一致**——细：sid33"一遍，然后道："
  是原行 29 的后半（行内切分）；粗：sid61 的 quote 拼接原行 63-65 三行
  （App 端合并显示），但同一位置还有 sid62/63 分别精确对应行 64/65
  （Web 端细分显示）。取细粒度为基准：sid61 只锚定行 63 首行，
  行 64/65 留给 sid62/63，互不吞并。
- **坑 3：5 个站点段落 txt 完全缺失**：sid18"朏朏"/sid25"小章居士沉默了。"
  /sid51"“你这人有点意思。”"/sid67"章羌叹了口气道："/sid96"“小章居士在家吗？”"
  /sid105"PS：周末已是单更。"（章末作者 PS，157 条评论挂在上面！）。
  以 quote 为权威文本按 sid 顺序注入到前后已锚定段落之间。
- 匹配策略：前缀锚定（quote 是段落前缀；支持 1~3 行窗口定位跨行段，
  但只锚定首行）+ 行内包含定位切分点 + 缺失注入，全部确定性匹配；
  保留 ch4 的 quote 引导单字修正兜底（本章为干净文本，预期 0 修正）。
"""

from __future__ import annotations

import argparse
import csv
import difflib
import json
import re
from collections import Counter
from copy import deepcopy
from pathlib import Path

from opencc import OpenCC

DEFAULT_CSV = Path(
    "/Users/moomin/Desktop/评论/outputs/35626462603382207/tagged_comments.csv"
)
DEFAULT_OUT = Path("comment-data-ch5.json")
CHAPTER_TXT = Path(
    "/Users/moomin/WorkBuddy/评论skill/outputs/chapters/表3_剑烛大荒_小章居士.txt"
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

# 起点广告位文字（txt 原行 22-27），按归一化文本精确剔除
ADS_RAW = [
    "冷艳女帝，痴情公主，征服女尊乱世！",
    "忍辱三年，夺丹夺宝夺圣女",
    "让你上交宗门，没让你娶妻成仙！",
    "天道酬勤，从山奴肝成长生武圣",
    "纯阳剑仙：我的老婆是女帝",
    "谷内无错  可以速读",
]

# 2026-10 v4 打标口径会把部分固定标签名也写进内容标签列（ch4 同款坑）
# 对齐得分阈值：仅用于 quote 引导错字修正
FIX_MIN = 0.85


def norm_text(value: str) -> str:
    """归一化：只保留汉字/字母/数字（去全部标点与空白，含 ￼ 等 emote 占位符）。"""
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", re.sub(r"\s+", "", value or ""))


def norm_with_map(value: str) -> tuple[str, list[int]]:
    """归一化并保留 norm 索引 → 原文索引 的映射（用于回原文字符位置切分）。"""
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
    rest = [ln.strip() for ln in lines[i + 1:]]
    while rest and not rest[0]:
        rest.pop(0)
    rest = [ln for ln in rest if ln]
    ads = {norm_text(a) for a in ADS_RAW}
    kept = [ln for ln in rest if norm_text(ln) not in ads]
    removed = len(rest) - len(kept)
    if removed != len(ADS_RAW):
        raise SystemExit(f"广告行剔除数 {removed} != 预期 {len(ADS_RAW)}，请核对 ADS_RAW")
    return kept


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


def check_monotonic(sid_to_pos: dict[int, int], stage: str) -> None:
    items = sorted(sid_to_pos.items())
    for k in range(len(items) - 1):
        if items[k][1] > items[k + 1][1]:
            raise SystemExit(f"{stage} 匹配非单调: sid{items[k]} -> sid{items[k+1]}")


def build_paragraphs(rows: list[dict]):
    """确定性 quote 锚定构建分段（ch5 专用，替代 ch3/ch4 的五阶段模糊匹配）：

    1) 广告行剔除（load_raw_lines）
    2) sid 升序 + 游标前缀锚定：quote 是段落前缀，在 1~3 行窗口里找
       startswith 命中 → 只锚定窗口首行（细粒度基准，行内剩余部分
       可被后续 sid 以行内切分占用；跨行段的后续行也可被后续 sid 锚定）
    3) 行内包含定位：quote 出现在某行中部 → 该行在此切分，段落起点=切点
       （开引号等前导标点归属新段）
    4) 完全缺失的 sid：以 quote 原文为段落文本，按 sid 顺序注入到
       前一已锚定段落的段落之后（无前者→开头；无后者→结尾）
    5) quote 引导单字修正兜底（干净文本，预期 0 处）
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

    # ---- 阶段 2：前缀锚定（sid 升序，游标推进） ----
    L = len(raw_lines)
    anchors: dict[int, tuple[int, int | None]] = {}  # sid -> (行号, 切分原文位置或 None)
    cuts: dict[int, list[int]] = {}  # 行号 -> [切分原文位置]
    prefix_failed: list[int] = []
    cursor = 0
    for sid in sorted(sid_nq):
        nq = sid_nq[sid]
        hit = None
        for n in range(cursor, L):
            matched_span = False
            for span in (1, 2, 3):
                if n + span > L:
                    break
                if "".join(line_norm[n:n + span]).startswith(nq):
                    hit = (n, None)
                    matched_span = True
                    break
            if matched_span:
                break
        if hit is None:
            prefix_failed.append(sid)
        else:
            anchors[sid] = hit
            # 游标只推进到锚定行（行内切分后同行的剩余部分仍可承载后续 sid）
            cursor = hit[0]
    check_monotonic({s: a[0] for s, a in anchors.items()}, "前缀锚定")

    # ---- 阶段 3：行内包含定位切分点（仅对前缀未命中 sid） ----
    # 夹在前后已锚定 sid 的行区间内找包含位置；有效性 = "恰好填满某个
    # 已有片段的尾部"（fragment-tail 规则）：
    #   - sid33"一遍，然后道："恰是原行 29 去掉 sid32 前缀后的尾部 → 真切分
    #   - sid18"朏朏"落在未锚定整行"…按着朏朏颈部道："中间、尾部还有
    #     "颈部道" → 假切分，走缺失注入
    # 另保留覆盖检查：包含位置被更小 sid 的前缀锚定 quote 覆盖 → 拒绝
    anchor_line = {s: a[0] for s, a in anchors.items()}
    anchor_cover = {s: len(sid_nq[s]) for s in anchors if anchors[s][1] is None}
    missing: list[int] = []
    for sid in prefix_failed:
        nq = sid_nq[sid]
        lo = max((ln for s2, ln in anchor_line.items() if s2 < sid), default=0)
        hi = min((ln for s2, ln in anchor_line.items() if s2 > sid), default=L - 1)
        hit = None
        for n in range(lo, hi + 1):
            pos = line_norm[n].find(nq)
            if pos <= 0:
                continue
            if any(s2 < sid and anchor_line[s2] == n and anchor_cover[s2] > pos
                   for s2 in list(anchors) if s2 in anchor_cover):
                continue  # 包含位置被更小 sid 的前缀 quote 覆盖 → 假切分
            # fragment-tail：quote 必须恰好填满该行某个已有片段的尾部
            frag_ends = sorted(cuts.get(n, [])) + [len(line_norm[n])]
            if not any(pos + len(nq) == e for e in frag_ends if e >= pos + len(nq)):
                continue
            raw_pos = line_map[n][pos]
            # 段首的开引号等前导标点归属新段：切点左移吃掉开标点
            while raw_pos > 0 and raw_lines[n][raw_pos - 1] in "“‘（《【":
                raw_pos -= 1
            if 0 < raw_pos < len(raw_lines[n]):
                hit = (n, raw_pos)
                cuts.setdefault(n, []).append(raw_pos)
                anchors[sid] = hit
                break
        if hit is None:
            missing.append(sid)
    check_monotonic({s: a[0] for s, a in anchors.items()}, "行内切分")

    # ---- 段落组装：行按切分点碎成片段，片段即段落 ----
    # frag_para: (行号, 片段起点原文位置) -> 段落 idx；片段起点 = 0 与各切分点
    paragraphs: list[str] = []
    frag_para: dict[tuple[int, int], int] = {}
    for n, p in enumerate(raw_lines):
        pts = sorted(set(cuts.get(n, [])))
        starts = [0] + pts
        ends = pts + [len(p)]
        for s, e in zip(starts, ends):
            if e > s:
                frag_para[(n, s)] = len(paragraphs)
                paragraphs.append(p[s:e])

    # sid -> 段落 idx（锚定行首 = 片段起点 0；锚定切分点 = 该切分片段）
    sid_to_idx: dict[int, int] = {}
    for sid, (n, cut_pos) in anchors.items():
        key = (n, 0) if cut_pos is None else (n, cut_pos)
        if key not in frag_para:
            raise SystemExit(f"sid{sid} 锚定片段缺失: 行{n} key={key}")
        sid_to_idx[sid] = frag_para[key]
    check_monotonic(sid_to_idx, "组装")

    # ---- 阶段 4：缺失段落注入（quote 为权威文本，按 sid 顺序插到前一锚定段之后） ----
    injected_info: list[tuple[int, int, str]] = []  # (sid, 段落idx, 文本)
    for sid in missing:  # missing 已升序
        prev_candidates = [idx for s2, idx in sid_to_idx.items() if s2 < sid]
        insert_at = (max(prev_candidates) + 1) if prev_candidates else 0
        text = sid_quotes[sid]
        paragraphs.insert(insert_at, text)
        for s2 in list(sid_to_idx):
            if sid_to_idx[s2] >= insert_at:
                sid_to_idx[s2] += 1
        sid_to_idx[sid] = insert_at
        injected_info.append((sid, insert_at, text))
    check_monotonic(sid_to_idx, "注入")
    for sid, at, text in injected_info:
        print(f"  注入缺失段: sid{sid} @段{at}: {text[:40]}")

    # ---- 阶段 5：quote 引导单字修正兜底 ----
    fixes: list[tuple[int, str, str, str]] = []
    for sid, para_idx in sorted(sid_to_idx.items()):
        nq = sid_nq.get(sid)
        if not nq or para_idx >= len(paragraphs):
            continue
        para = paragraphs[para_idx]
        np_, idx_map = norm_with_map(para)
        sm = difflib.SequenceMatcher(None, nq, np_, autojunk=False)
        if sm.ratio() < FIX_MIN:
            continue
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "replace" and (i2 - i1) == 1 and (j2 - j1) == 1:
                old, new = np_[j1], nq[i1]
                if old != new and T2S.convert(new) == new and T2S.convert(old) == old:
                    fixes.append((para_idx, old, new, para[max(0, idx_map[j1]-6):idx_map[j1]+7]))
                    para = para[:idx_map[j1]] + new + para[idx_map[j1]+1:]
        paragraphs[para_idx] = para

    unmatched_sids = sorted(
        s for s in sid_nq if s not in sid_to_idx
    )
    return paragraphs, sid_to_idx, fixes, unmatched_sids, len(ADS_RAW)


def build_payload(csv_path: Path) -> dict:
    rows = list(csv.DictReader(open(csv_path, encoding="utf-8-sig")))
    paras, sid_to_idx, fixes, unmatched_sids, ad_removed = build_paragraphs(rows)

    print(f"段落构建: {len(paras)} 段（剔除广告行 {ad_removed} 行），"
          f"锚定 {len(sid_to_idx)} sid，错字修正 {len(fixes)} 处")
    for pidx, old, new, ctx in fixes:
        print(f"  段{pidx}: {old}->{new}  …{ctx}…")
    print(f"未匹配 sid: {unmatched_sids}")

    def target_of(row) -> int:
        sid = get_sid(row)
        # 章评两入口：sid=-1（标题节点）与 sid=0（章末"本章说"）——与 ch1-ch4 同口径
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
        # v4 打标口径：固定标签名出现在内容标签列时提升合并进 fixedTags
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
        "built chapter5 comment data: "
        f"{stats['mainCount']} main, {stats['replyCount']} replies, "
        f"{stats['paragraphTargetCount']} paragraph targets, "
        f"{stats['chapterTotalCount']} chapter comments, "
        f"{stats['orphanReplyCount']} orphans, tag-matched {stats['tagMatchedCount']}"
    )


if __name__ == "__main__":
    main()
