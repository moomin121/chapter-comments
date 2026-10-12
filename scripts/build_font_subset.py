#!/usr/bin/env python3
"""Rebuild fonts/lxgw-wenkai-gb-500.woff2.

子集 = GB2312 一级常用字（3755 字）+ chapters/*.txt 全部正文字符 + index.html
CHAPTERS 段落数组字符 + ASCII 可打印区 + 常用中英标点。

接入新章节后重跑本脚本即可（字体文件名不变，无需改 HTML）；
子集字体仅 500 字重（页面 --wenkai 元素统一 500）。
"""

from __future__ import annotations

import html
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHAPTERS_DIR = Path("/Users/moomin/WorkBuddy/评论skill/outputs/chapters")
SRC_TTF = Path("/tmp/LXGWWenKaiGB-Medium.ttf")
OUT_WOFF2 = ROOT / "fonts" / "lxgw-wenkai-gb-500.woff2"
CHARS_FILE = Path("/tmp/wenkai-subset-chars.txt")

EXTRA = (
    "".join(chr(c) for c in range(0x20, 0x7F))  # ASCII 可打印区
    + "，。、；：？！“”‘’（）《》〈〉【】…—·～￥％℃°①②③④⑤⑥⑦⑧⑨⑩"
    + "〇（）丶冫氵忄钅纟饣礻衤"
)


def gb2312_level1() -> str:
    """GB2312 一级字库（0xB0A1-0xD7F9），覆盖现代中文 99% 用字。"""
    chars = []
    for hi in range(0xB0, 0xD8):
        for lo in range(0xA1, 0xFF):
            try:
                ch = bytes([hi, lo]).decode("gb2312")
                chars.append(ch)
            except UnicodeDecodeError:
                pass
    return "".join(chars)


def collect_chapter_chars() -> str:
    texts: list[str] = []
    # 1) chapters/*.txt 全部正文章节（含未来要接入的）
    if CHAPTERS_DIR.exists():
        for f in sorted(CHAPTERS_DIR.glob("表*.txt")):
            texts.append(f.read_text(encoding="utf-8"))
    # 2) index.html 内联段落数组（CHAPTERS.ch1/ch2.paragraphs 的 JS 字符串）
    idx = (ROOT / "index.html").read_text(encoding="utf-8")
    for m in re.finditer(r"'((?:[^'\\]|\\.)*)'", idx[idx.find("var CHAPTERS"):idx.find("// GENERATED_COMMENT_DATA_START")]):
        texts.append(m.group(1).encode().decode("unicode_escape", errors="ignore"))
    return "".join(texts)


def main() -> None:
    if not SRC_TTF.exists():
        sys.exit(f"缺少源字体 {SRC_TTF} —— 先下载 LXGWWenKaiGB-Medium.ttf v1.522")
    all_chars = set(gb2312_level1() + collect_chapter_chars() + EXTRA)
    all_chars.discard("\n")
    all_chars.discard("\r")
    charset = "".join(sorted(all_chars))
    CHARS_FILE.write_text(charset, encoding="utf-8")
    print(f"子集字符数: {len(charset)}")

    subprocess.run(
        [
            "/Users/moomin/.workbuddy/binaries/python/envs/default/bin/pyftsubset",
            str(SRC_TTF),
            f"--text-file={CHARS_FILE}",
            f"--output-file={OUT_WOFF2}",
            "--flavor=woff2",
            "--layout-features=*",
            "--no-hinting",
            "--desubroutinize",
        ],
        check=True,
    )
    size = OUT_WOFF2.stat().st_size
    print(f"输出: {OUT_WOFF2} ({size / 1024:.0f} KB)")

    # 校验：章节正文的每个字符必须都在子集里（pyftsubset 只保留能编码的字形）
    font_chars = charset  # --text-file 的字面近似；真正校验用 fontTools
    from fontTools.ttLib import TTFont

    font = TTFont(OUT_WOFF2)
    cmap = font.getBestCmap()
    missing = [ch for ch in charset if ord(ch) not in cmap and ch.strip()]
    missing = [ch for ch in missing if ord(ch) >= 0x4E00]  # 忽略标点/控制
    if missing:
        print(f"⚠️ 仍有 {len(missing)} 个汉字缺字形: {''.join(missing[:50])}")
    else:
        print("校验通过：章节文本全部汉字均有字形")


if __name__ == "__main__":
    main()
