# 章节评论页 · chapter-comments

起点风格的小说章节阅读页 + 段评气泡 + 评论抽屉。基于 Figma 稿 + qidian.com 章节页实现。

## 这是什么

把 write.html（原 1.3MB）拆成两个独立网页后的**评论模块独立项目**。和根目录 `write.html`（专注监测页）解耦，可单独启动、修改、部署。

- **根目录 `write.html`**：摄像头专注监测 + 字数统计（编辑工具）
- **`chapter-comments/index.html`**：章节阅读页 + 段评气泡 + 评论抽屉（读者视角，本目录就是这个）

## 文件结构

```
chapter-comments/
├── index.html        # 单文件应用：HTML + CSS + JS 全部内联（71KB）
├── README.md         # 本文件
├── CLAUDE.md         # 给 Codex / Claude 看的项目约定
└── screenshots/      # 渲染效果截图（可选）
```

单文件设计的好处：方便协作开发时直接 diff `index.html`；坏处：行号会随编辑而变，所以定位问题时用 grep + 注释关键字更稳。

## 怎么运行

任意 HTTP 静态服务器都行（file:// 直接打开会受 CORS 限制）：

```bash
cd chapter-comments
python3 -m http.server 8211        # 或用项目根的 server.py
open http://127.0.0.1:8211/index.html
```

## URL 参数

- `?cm=para-N`：直接定位到第 N+1 段（0 基），自动高亮 + 切段评视图
- 无参数：默认直接进入评论模式（阅读视图 + 抽屉自动展开）

## 主要交互

| 操作 | 效果 |
|---|---|
| 点击右侧栏 ✕ 或右上 × | 关闭评论抽屉 → 回到编辑态（但本页无编辑态，关闭后是空白） |
| 点击段落末尾的彩色气泡 | 段落高亮 + 抽屉切到「第 N+1 段 · X 条评论」 |
| 段评 tab | 按热度列出本章各段，点击跳转 + 高亮 |
| 全部 tab | 章评主楼 + 楼中楼回复（展开/收起） |
| 顶部 ← 返回全部评论 | 从段评视图回到全部评论 |
| 排序 tab：默认 / 最热 / 最新 / 长评 | 全部评论 + 单对象视图共用，默认按 sortValue 升序、对象总评论数降序、`createdAt` 倒序、正文字数倒序 |

## 排序模式

`sortComments()` 提供四种 comparator，详情见 `doc/技术方案.md` §4 与 `prd.md` §10.4：

| 排序 | 全部评论视图 | 单对象视图 |
|---|---|---|
| 默认 | 聚合块：章评 → 段落序 → 未匹配；块内 sortValue 升序兜底点赞降序 | 一级评论 sortValue 升序 |
| 最热 | 聚合块按对象 totalCount 降序；未匹配最后；块内点赞降序 | 一级评论点赞降序 |
| 最新 | 不聚合，拍平按 `createdAt` 倒序；带原文引用行 | 一级评论 `createdAt` 倒序 |
| 长评 | 不聚合，拍平按正文字符数（去空白）倒序；带原文引用行 | 一级评论正文字符数倒序 |

## 热力色阶

段评气泡与侧栏引用行计数气泡统一按三档红系渐进（PRD §8.4）：

| 数量 | 颜色 | 十六进制 |
|---|---|---|
| ≥ 100 | 品牌红 | `#FF3B4F` |
| 30 – 99 | 琥珀 | `#C87A16` |
| < 30 | 灰 | `#6F737A` |

颜色映射在 `<script>` 内 `function heatClass(n){...}`，`.para-bubble` / `.chap-bubble` / `.cm-ref-bubble` 三处共用。

## 数据来源

`index.html` 中的 `var CHAPTER = {...}` 块定义了：
- `title`：章节标题
- `meta.{work,author,words,time}`：作品名 / 作者 / 字数 / 发布时间
- `chapterCommentCount`：章评总数（标题旁的红胶囊 + 抽屉标题）
- `paragraphs`：190 段正文（来自起点章节页 OCR）
- `SECTION_COUNTS`：190 段对应的段评数（与 `paragraphs` 严格一一对应）

**改数据**：直接编辑 `var CHAPTER = {...}` 和 `var SECTION_COUNTS = [...]`。两个数组长度必须一致，否则 `renderReader` 里的循环会溢出。

## 关键 DOM id

修改时优先按 id 定位：

| id | 用途 |
|---|---|
| `#paper` | 正文容器 |
| `#reader` | 阅读视图（段评气泡的父容器） |
| `#paraList` | 段落列表（JS 注入到此处） |
| `#chapTitle` | 章节大标题 |
| `#chapWork` / `#chapAuthor` / `#chapWords` | 元信息里的作品名 / 作者 / 字数 |
| `#chapSecTotal` | 章节头部"本章含 X 条段评" |
| `#chapBubble` | 标题旁的章评数红胶囊 |
| `#cmDrawer` | 评论抽屉 |
| `#cmBadge` | 右侧栏评论按钮的红点 |
| `#cmCount` / `#cmTabAll` / `#cmTabPara` / `#cmBack` / `#cmClose` | 抽屉内部 |
| `#cmList` | 评论列表容器 |
| `#cmInput` | 底部输入框 |
| `#chapterList` | 左侧章节列表容器 |

## 开发注意事项

- 数据是**OCR 三轮交叉验证**得来，部分段落数字可能仍有 ±1 误差，详见项目根的 `.workbuddy/memory/2026-09-02.md` 第六轮。
- 评论用户头像颜色是 `avatarColor(user)` 8 色哈希循环（`#5C8AFF`、`#1E71EF`、`#9A6CFF`、`#1EBD8E`、`#FF7A45`、`#E84D2F`、`#14B8A6`、`#0EA5E9`）。
- 章节列表是硬编码 16 章（写在小段 script 里），没接到真实接口。
- localStorage key `wb_comment_mode` 记忆评论开关，但本页默认开启，可忽略。