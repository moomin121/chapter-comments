# CLAUDE.md — 章节评论页 · Codex 上下文

> 这是给 Codex / Claude Code / WorkBuddy 等 AI 工具读的项目说明。人类开发者请看 [README.md](README.md)。

## 项目一句话总结

轻量静态网页 `index.html`，起点风格的小说章节阅读页 + 段评气泡 + 评论抽屉。HTML + CSS + JS 保持无构建入口，完整评论数据拆到 `comment-data.json` 异步加载。190 段章节正文 + 170 个段评气泡（真实 CSV 聚合，4465 条一级评论 + 3028 条回复）。

---

## 接手必读：三条硬约束

这是此前开发中反复踩坑换来的，动代码前先读这三条。

### 1. 右侧图标栏必须始终贴 viewport 最右边缘

需求原话：「右侧工具栏始终在整个网页的最右侧」。

`.body-row` 是 flex 容器，四个主区靠 `order` 排次序，**不能靠 DOM 顺序**：

```css
.leftpanel   { order: -2; }   /* 章节列表，最左 */
.center      { order:  0; }   /* 正文（默认，不用显式写） */
.cm-drawer   { order:  1; }   /* 评论抽屉，展开时插在正文与图标栏之间 */
.rightrail   { order:  2; }   /* 图标栏，永久最右 */
```

**踩过的坑**：曾经把 `.rightrail` 也写成 `order: 1`，与 `.cm-drawer` 撞了。同 order 时 flex 按 DOM 顺序排，而 `cm-drawer` 在 DOM 里排在 `rightrail` 之后 → 抽屉展开时反而把图标栏挤到中间，右边空出 360px 的缝。

**验证必须用像素探针，不能只看截图**：

```js
var r = document.querySelector('.rightrail').getBoundingClientRect();
innerWidth - r.right   // 必须 === 0，不论抽屉开还是关
```

肉眼看截图会误判——抽屉宽 360px 加上图标栏 48px 连成一片，看起来像"贴右了"，实际中间被挤开了。

### 2. 评论数字必须来自真实数据，不能编造

需求原话：「评论数字要对」。

数字现在来自真实 CSV（`谁让他修仙的第1章评论_作者视角打标.csv`），由 `ensureCommentIndex()` 按评论对象（标题/段落）聚合"一级+回复"得出。首屏气泡数量先读 `index.html` 里的轻量 `targetTotalCounts`，完整评论到达后再用 `comment-data.json` 重建索引。改数据只能改 CSV 后重跑 `build_comment_data.py --update-all`，**不要手改页面里的数字**，也不要为了"让每段都有气泡"编数字。

### 3. 不要引入构建系统

当前刻意保持静态 HTML 架构，只有评论数据外置为 `comment-data.json`。见「不要做的修改」。

## 技术栈

- **纯原生**：HTML + CSS + 原生 JS（无构建步骤、无依赖、无打包）
- **字体**：正文/标题使用 `LXGW WenKai GB` 500 字重，**本地子集** `fonts/lxgw-wenkai-gb-500.woff2`（231KB，仅含正文用到的 1049 字符 + ASCII + 常用标点），`font-display:block` + preload 零闪烁。⚠️ 两条教训：(1) 不要手写 `@font-face` 指向 `lxgw-wenkai-webfont` 包根目录的 `.woff2`——404；(2) 不要用 CDN 的 unicode-range 分片 CSS——每段文字命中多个分片、陆续到达，正文会"系统字体⇄文楷"反复闪烁。正文文字有新增时需重新子集化（pyftsubset --text-file）
- **数据**：正文在 `var CHAPTER = {...}`；轻量评论元数据在 `// GENERATED_COMMENT_DATA_START/END` 之间；完整评论在 `comment-data.json`（脚本生成，勿手改）
- **头像**：评论头像为 `avatars/a01~a64.webp`（64 张 DiceBear **personas** 风格，64×64，合计 256KB），**中国化面孔**：`skinColor` 锁定黄肤色系（eec39a/e8b98d/dfae82…）、`hairColor` 锁定纯黑 `1b1410`、发型只用中式（bobBangs/shortCombover/straightBun/bobCut/curlyBun/双马尾/丸子头等 14 种），1/4 胡须 + 1/4 眼镜 + 其余干净脸。`avatarHtml()` 按 guid 哈希稳定分配——同一读者永远同一张。图片下方保留 `avatarColor` 色块 + 名字末字，加载失败自动回退。⚠️ 换风格时注意：micah 的 `baseColor` 最浅只到粉红 `f9c9b6` 且指定 `hair` 极易变秃头，**调不出中国面孔**；personas 的 `skinColor`/`hairColor` 支持任意十六进制，才是正解
- **存储**：`localStorage.wb_comment_mode` 记忆评论开关（默认开启，可忽略）

## 文件边界

```
chapter-comments/index.html                  # 静态入口（HTML + CSS + JS + 轻量元数据）
chapter-comments/comment-data.json           # ch1 完整评论数据（脚本生成）
chapter-comments/comment-data-ch2.json       # ch2 玄鉴仙族_相累 评论数据（脚本生成）
chapter-comments/comment-data-ch3.json       # ch3 夜无疆_杀穿诸敌 评论数据（脚本生成）
chapter-comments/comment-data-ch4.json       # ch4 廓晋_涨水（中） 评论数据（脚本生成）
chapter-comments/comment-data-ch5.json       # ch5 剑烛大荒_小章居士 评论数据（脚本生成）
chapter-comments/scripts/build_comment_data.py     # ch1 CSV → 元数据块 + comment-data.json
chapter-comments/scripts/build_chapter2_data.py    # ch2 CSV → comment-data-ch2.json
chapter-comments/scripts/build_chapter3_data.py    # ch3 CSV → comment-data-ch3.json（含 OCR 修正/分段重建）
chapter-comments/scripts/build_chapter4_data.py    # ch4 CSV → comment-data-ch4.json（quote 匹配驱动分段）
chapter-comments/scripts/build_chapter5_data.py    # ch5 CSV → comment-data-ch5.json（前缀锚定+缺失段注入）
chapter-comments/scripts/build_font_subset.py      # 字体子集重建（接入新章节后必跑）
chapter-comments/test/smoke-test.sh          # 冒烟测试 v2（390 项，pre-commit 强制跑）
chapter-comments/prd.md                      # 产品需求（数据契约/验收标准）
chapter-comments/doc/技术方案.md              # 技术方案（路线/排序策略/测试方案）
chapter-comments/CLAUDE.md                   # 本文件
chapter-comments/README.md                   # 人类开发文档
```

**不要引入构建项目**：保持原生静态架构；性能优化优先通过数据瘦身、异步加载和按需渲染完成。

## 关键代码定位（用注释关键字搜索）

以下注释在 `index.html` 里都唯一，定位用 grep 即可：

| 注释关键字 | 作用 |
|---|---|
| `/* ============ 章节阅读视图（含段评气泡 / 评论抽屉） ============ */` | 段评气泡 + 评论抽屉 CSS 起始 |
| `.cm-drawer{` | 评论抽屉容器 CSS |
| `// 0) 示例章节：` | CHAPTER 数据块起始 |
| `// GENERATED_COMMENT_DATA_START` | 真实评论数据块（脚本生成区） |
| `// 1) 工具` | `$(s)` / `escapeHtml` / `heatClass` / `avatarColor` / `getParagraphByTarget` / `scrollToTarget` 工具函数 |
| `// 2) 渲染 reader` | `renderReader()` 渲染段落 + 气泡 |
| `// 3) 段选择联动` | `selectParagraph(idx)` → `enterTargetView(targetId)` 进单对象视图 |
| `// 4) 渲染单对象评论列表` | `renderTargetComments(targetId)` 该对象全部一级评论 |
| `// 5) 渲染全部评论` | `renderAllComments()` AI 卡 + 章节标题评论 + 按段聚合 + 未匹配兜底 |
| `// 6) 段评 tab` | `renderParagraphsOverview()` 段评导航 |
| `// 7) 模式控制：评论模式开关` | `setCommentMode(on)` / `switchCmTab(name)` |

## 数据契约

```js
var CHAPTER = {
  title: '...',                    // 章节标题
  meta: {work, author, words, publishedAt, visibility},
  paragraphs: ['段1', '段2', ...]  // 190 段
};
// GENERATED_COMMENT_DATA_START ... END 之间的 COMMENT_DATA 轻量元数据（由脚本生成，勿手改）
// 完整评论数据在 comment-data.json（由脚本生成，勿手改）
```

## 多章节架构（2026-10-12 ch2 / 2026-10-13 ch3、ch4、ch5 接入）

- **CHAPTERS 注册表**（index.html）：`ch1~ch5` 五章，每章含 `treeName/treeWc/commentDataUrl/aiSummary/title/meta/paragraphs`。目录点击 → `switchChapter(id)` 整章替换正文/评论数据源/AI 卡并复位全部视图状态；左侧目录条目用 `data-cid` + `app:switch-chapter` 事件。
- **评论数据按章外置**：`comment-data.json`（ch1）/ `comment-data-ch2.json` ~ `ch5`，均由对应 build 脚本从 58 列合体 CSV 生成（起点后台导出 49 列 + 作者视角打标 8 列，2026-10-12 v4 口径）。
- **segmentId 语义（重要，分章实测）**：`extend1.segmentId` 在 ch2/ch3 是**全书级段落编号**，但在 **ch4 是本章级编号（1~63，与 ugc_level3_id 完全一致）**——都不能直接当段落索引用，必须靠 `quote_msg`（被评段落原文）匹配建立映射。特殊值：`sid=-1` = 章评标题节点（quote=章节标题）；**`sid=0` = 章末"本章说"（无 quote、内容为催更/进度讨论），与 ch1 CSV"段落ID=0 视为章评"同一口径，归入章评 -1**（ch2 曾误归未匹配，2026-10-13 修正，章评 75→119）；`sid=-110` 等 = 混入的其他章评论 → 未匹配模块。
- **ch4（廓晋_涨水（中））数据的两个坑**（build_chapter4_data.py 已处理）：
  1. v4 打标口径会把部分**固定标签名（建议/捉虫/好评/疑问）也写进内容标签列**——同名标签在 build 时提升合并进 fixedTags，避免 tagCounts 重名胶囊与单条评论标签重复（建议 34=固定8∪内容26 并集；筛选按 commentTags() 合并匹配，口径不变）；
  2. sid=13（"确实很得用。"）/20（"刘乘点点头。"）的 quote 是站点段落里的短对话行，txt 里完全缺失 → 未匹配模块（与 ch3 缺失行同型）；quote 引导修正 1 处（段48"确系→确实"，以站点 quote 为权威）。
- **ch3（夜无疆_杀穿诸敌）正文的三个坑**（build_chapter3_data.py 已处理）：
  1. 源 txt 是 OCR 转写，含系统性错字（苌→长、二→两、此→比、哀鸣→长鸣、全身→金身等 15 处）——用 quote 做权威文本反查修正；
  2. txt 分行比站点分段更细/更粗（166 行 vs 站点段落）——quote 是段落前缀，按"各 sid 段落起点=行内切分点 + 窗口匹配合并跨行段"重建出 167 段；
  3. quote 有繁体（读者端繁体显示）——opencc t2s 归一后匹配。
  9 个 sid 引用的短对话行在 txt 里完全缺失（如"玉京魔。""长公主！"），评论归入未匹配模块。
- **ch5（剑烛大荒_小章居士）数据的三个坑**（build_chapter5_data.py 已处理，匹配策略与 ch3/ch4 不同：确定性前缀锚定，非五阶段模糊匹配）：
  1. txt 混入 6 行起点广告位文字（原行 22-27"冷艳女帝…"等），按精确文本剔除；
  2. 站点分段粒度不一致：sid33"一遍，然后道："是行 29 后半（行内切分，fragment-tail 规则判定）；sid61 的 quote 跨行 63-65 三行（App 端合并显示），但 sid62/63 恰好精确对应行 64/65（Web 端细分）——取细粒度为基准，sid61 只锚定首行；
  3. 6 个站点段落 txt 完全缺失，以 quote 为权威文本按 sid 顺序注入：sid18"朏朏"/sid25"小章居士沉默了。"/sid51/sid67/sid96"小章居士在家吗？"/sid105"PS：周末已是单更。"（章末作者 PS，157 条评论挂上面）。**坑中坑**：sid18"朏朏"曾被误判为行内切分（切在别的段落中间），靠 fragment-tail 规则（quote 必须恰好填满片段尾部）排除。
- **接入新章节清单**：写 `scripts/build_chapterN_data.py` → 生成 `comment-data-chN.json` → index.html 的 CHAPTER_TREE 加目录项 + CHAPTERS 注册（含 aiSummary）→ 重跑 `build_font_subset.py` → smoke-test.sh 加 N 章断言块（含"目录仅N个可切换章节"锚点更新）→ 全量跑通 → commit。

**评论数据已接入真实 CSV**（2026-09-04）：
- 来源：`/Users/moomin/Documents/ChatGPT/New project/outputs/who_made_him_cultivate_ch1_comments/谁让他修仙的第1章评论_作者视角打标.csv`
- 重建：`python3 scripts/build_comment_data.py --update-all`（dry-run 校验：去掉 `--update-all`）
- 规模：7493 行 → 4465 条一级评论 + 3028 条回复（其中 663 条孤儿回复不展示）、172 个有评段、章评 621 条
- `SECTION_COUNTS / SECTION_POOL / COMMENT_TAGS` 等演示数据已删除；气泡计数由 `ensureCommentIndex()` 按评论对象聚合得出
- CSV 更新后必须重跑 build 脚本并同步更新 `test/smoke-test.sh` 的数据锚点

**注意**：`update_index` 必须用 lambda replacement（脚本已修），否则 `re.subn` 会把 block 里的 `\\` 解释成单个 `\` 污染数据。

## 不要做的修改

1. **不要改 `function $(s)` 的实现** — 是大量脚本的全局工具函数，改名会牵动 50+ 处调用
2. **不要把内联 CSS/JS 拆成构建项目** — 当前是纯原生静态架构；评论数据外置是性能需要
3. **不要引入新依赖**（jQuery、Vue、Tailwind 等）— 当前是纯原生架构，加依赖会把静态页变成构建项目

## 加新功能时的模式

例如「在评论抽屉顶部加个「只看我的关注」开关」：

1. **DOM**：在 `<aside class="cm-drawer" id="cmDrawer">` 里 `<div class="cm-toolbar">` 旁边加一个 `<div class="cm-follow-toggle">`
2. **CSS**：在 `.cm-toolbar{...}` 附近加 `.cm-follow-toggle{...}`
3. **JS**：在 `// 7) 模式控制：评论模式开关` 附近加 `function toggleFollowOnly(){...}`，并在 `renderAllComments` / `renderTargetComments` 里调用时检查状态

始终遵循：**数据契约不变 → 渲染函数增加过滤条件 → 不破坏现有 DOM 结构**。

## 已知数据边界（真实 CSV，2026-09-05）

- **CSV 段落ID 是 1-based**（与正文 0-based idx 错 1 位）：build_comment_data.py 通过 `normalize_target_id()` 把 `targetId >= 1` 都 -1 转成 0-based；-1 保留为章评；0 视为章评（CSV 里"阅～～～"类评论对象为空、正文是章评风格）。**改这个之前要先验证：build 脚本统计 idx=17 应等于 257（OCR 旧 SECTION_COUNTS[17]=257），吻合=偏移正确**。
- **越界段**：CSV 中 `段落ID = 191` 偏移后 targetId=190 仍超出正文 idx 0-189 范围，按 PRD §14.3 归入"未匹配评论对象"分组，展示在章评块之后（`.cm-unmatched-module`，仅 1 个）。
- **孤儿回复**：663 条回复的父级评论不在 CSV 内，按 PRD §14.6 不展示，仅在 build 统计里记录。
- **昵称/头像/用户标签**：CSV 无真实昵称头像，昵称显示 `用户guid`，头像按 guid 哈希 8 色 + 昵称首字，用户标签隐藏（PRD §6 兜底策略）。
- **排序**：`自定义排序` 全为 -1，默认按点赞数降序 + 原始行号稳定兜底（PRD §4 / 技术方案 §4）。

## 当前数据快照（真实 CSV，1-based 偏移后）

```
段落数            190
有气泡的段         170
无气泡的段          20
有效评论总数      6830（一级 4465 + 挂载回复 2365）
段评总数          6098
章评数            732（含 targetId=0 归入的 111 条章评类）
有评段            171
聚合块            172（170 段块 + 1 章评块 + 1 未匹配块）
标签数            30（全部 + 13 固定 + 16 内容）
作品名            谁让他修仙的第1章（CSV）/ 没钱修什么仙？（页面 CHAPTER）
章节标题          第1章 面试
热度 Top 5 (idx): 27(366) / 60(278) / 40(268) / 18(257) / 132(253)
```

## 已知 UI 修正记录（2026-09-05）

- **AI 总结卡筛选可见**：仅在 `currentCommentTag === '全部'` 时显示；标签筛选态隐藏（focus 在真实命中上）
- **标签云样式**：截图/Codex 交接版的自然宽度 flex-wrap 紧凑胶囊 + emoji 前缀（固定标签）+ 数字后置；仅展示截图中的固定标签与高频内容标签，筛选仍使用 CSV 原始标签名；"全部"选中态蓝边白底蓝字；hover 蓝弱底蓝字
- **章节标题评论位置**：`targetId=-1` 的章评块紧跟 AI 总结卡，排在第一个段评块之前；未匹配对象仍放在最后
- **筛选后自动滚动**：标签 click listener 末尾 `#cmList.scrollTop = 0`
- **评论对象气泡可点击**：`.cm-ref-bubble` 加 `data-target-id` + cursor pointer + hover 高亮；在 bindTargetAnchors 里直接绑定 click（stopPropagation 防双重触发）
- **评论底部操作**：日期 + IP 地址 + 评论图标 + 点赞图标 + "赞"字 + 点赞数 + ···（提取 `commentMetaRow()` helper 复用）

## 测试入口

- `index.html`：默认直接进入评论模式（阅读视图 + 抽屉自动展开 + 全部评论聚合视图）
- `index.html?cm=para-17`：跳到第 18 段（idx=17，257 条评论），验证单对象视图 + 高亮
- `index.html?cm=para-0`：跳到第 1 段（105 条评论，"到了吗？"），验证 idx=0 段的气泡档位 + 单对象视图滚动

## 验证方法

### 首选：跑冒烟测试（改完必做，pre-commit hook 会强制跑）

```bash
cd chapter-comments
./test/smoke-test.sh
```

`test/smoke-test.sh` v2（2026-09-04 重写）分两段：

**A. 数据预处理段**（无浏览器）：跑 build 脚本校验统计（4465 一级 / 2365 挂载回复 / 663 孤儿 / 172 有评段）+ 校验 `index.html` 轻量元数据块和 `comment-data.json` 与 CSV 最新构建一致（防止改了 CSV 忘记 `--update-all`）。

**B. 页面渲染段**（agent-browser）：390 项断言覆盖 PRD §16 十二条验收 + 多章节切换：

| 类别 | 断言 |
|---|---|
| 默认态 | 抽屉展开 / 全部评论视图 / 有效评论总数 6830 |
| 气泡 | 190 段 / 170 气泡 / 标题胶囊 621 / 段评总数 6209 |
| 聚合视图 | AI 卡置顶 / 172 块 / 章评在首段之前 / 未匹配兜底 / 每段前 3 条 + 查看入口 |
| 单对象视图 | 全部一级评论 / 高亮 / 返回按钮 / 楼中楼展开收起 |
| 标签筛选 | 真实标签"这不就是现实/网贷还债太真实"过滤生效 / 全部还原 |
| 定位 | hover 临时高亮 + 不改筛选状态 / 点击进单对象视图 |
| 布局铁律 | 图标栏贴右 gap==0（抽屉开、关两态） |

**加新功能时同步往这个脚本里加断言**，别只手动点两下就说完成。

**数据锚点提醒**：CSV 更新后，先 `--update-all`，再同步改 smoke-test 里 `170 / 172 / 6830 / 257条 / 732条` 等锚点数字。

### 手工探针（调试用）

需要临时验证时：

```bash
cd /Users/moomin/WorkBuddy/编辑器 && python3 server.py 8210
agent-browser open "http://127.0.0.1:8210/chapter-comments/index.html"
agent-browser eval "document.querySelectorAll('.para').length"
```

要点：
- **布局问题必须用 `getBoundingClientRect()` 量像素**，不要只看截图——抽屉 360px 加图标栏 48px 连成一片，肉眼会误判成"已经贴右了"
- `.para-bubble[data-idx="17"]` 这类选择器在 shell 里引号容易冲突，用 `eval` + 转义双引号，或直接用 `?cm=para-N` URL 参数更可靠

## 开发流程规范（用户 agent.md 明确要求）

1. **每次改动后必须创建对应的 Git commit** —— 一个逻辑改动一个 commit，方便追踪和回滚
2. **每次改动后必须编写或更新测试，交付前跑通全部验证** —— 即上面的 `./test/smoke-test.sh`

本机 git 注意事项：
- 全局未配 `user.name`/`user.email`，本仓库已用局部配置（`moomin` / `moomin@local`）
- 提交时加 `-c commit.gpgsign=false`，本机未配 GPG 签名，否则提交会失败

## 交接状态（截至 2026-09-04）

已完成：

- [x] 从 `write.html`（1.3MB 混合体）拆出为独立页面，去掉 1.25MB base64 视频和专注监测逻辑
- [x] 正文替换为《没钱修什么仙？》第 1 章，190 段 + 段评数（OCR 三轮交叉验证）
- [x] 段评气泡 5 档热力色阶
- [x] 点击气泡 → 段落高亮 + 抽屉切段评视图
- [x] 段评 tab（按热度列出全部 190 段，点击跳转）
- [x] 章评主楼 + 楼中楼展开/收起
- [x] 右侧图标栏永久贴最右（flex order 修正）
- [x] git 仓库初始化，首次提交 `df3d5ac`
- [x] **真实评论数据接入**（2026-09-04）：CSV 7493 行经 `scripts/build_comment_data.py` 生成评论数据，替换全部 SECTION_POOL/SECTION_COUNTS/COMMENT_TAGS 演示数据；气泡/计数全部按评论对象聚合
- [x] **全部评论视图按段聚合**（PRD §10）：AI 总结卡置顶 → 按段顺序聚合块（前 3 条 + 查看本段入口）→ 章评块最后 → 未匹配对象兜底
- [x] **单对象视图全部一级评论**（PRD §12）：气泡/评论对象/查看入口点击进入，不再截断 2 条；返回全部评论按钮
- [x] **标签真实筛选**（PRD §11.3）：点击标签过滤一级评论并按对象聚合重渲染；"全部"还原
- [x] **评论对象定位**（PRD §13）：hover 滚动 + hover-preview 临时高亮；click 进单对象视图（标签复位全部）；章评气泡点击进章评视图
- [x] **默认排序兜底**（PRD §4）：sortValue 优先，-1 时点赞数降序 + 行号稳定
- [x] **冒烟测试 v2**（60 项，按 PRD §16）+ `.git/hooks/pre-commit` 强制跑测试
- [x] 修复 build 脚本 re.subn 转义 bug（数据块曾被去转义污染）
- [x] **CSV targetId 1-based 偏移修复**（2026-09-05）：build_comment_data.py normalize_target_id() 处理；idx=17 段评论从 5 → 257（吻合 OCR 旧数据）；章评数 621 → 732（targetId=0 的"阅"类评论归入）
- [x] **AI 总结卡仅"全部"筛选时显示**（2026-09-05）
- [x] **标签云重做**（2026-09-05）：4 列 flex-wrap 药丸形 + 固定标签 emoji 前缀（👍/🍅/💡/❓/👈/📚/🎬/🐛/🍚/⭐/🚫/✨）+ 数字后置
- [x] **标签筛选后自动滚到列表顶部**（2026-09-05）
- [x] **评论对象气泡点击触发单对象视图**（2026-09-05）：.cm-ref-bubble 加 data-target-id + cursor pointer + hover 高亮 + 直接绑定 click
- [x] **评论底部操作按 Figma 设计稿实现**（2026-09-05）：日期 + IP 地址 + 评论图标 + 点赞"赞"字 + 点赞数 + ···（commentMetaRow helper 复用）
- [x] 冒烟测试 v3（60 项，新增 11 项覆盖以上 6 个修正点）
- [x] **首屏性能优化**（2026-09-07）：`index.html` 从 3.88MB 降到约 163KB；完整评论拆到 `comment-data.json` 异步加载；保留原 LXGW WenKai 字体观感；冒烟测试扩展到 271 项
- [x] **多章节切换 + ch2 玄鉴仙族_相累**（2026-10-12）：CHAPTERS 注册表 / switchChapter 整章替换 / comment-data-ch2.json；冒烟测试加 ch2 断言块
- [x] **ch3 夜无疆_杀穿诸敌接入**（2026-10-13）：comment-data-ch3.json（1968 主评 + 588 回复，章评 483，167 段）；quote 驱动的 OCR 错字修正与分段重建；ch2 sid=0 归章评口径修正（75→119）；字体子集重建（898KB，含 ch2 漏跑的补课）；冒烟测试扩到 335 项
- [x] **ch4 廓晋_涨水（中）接入**（2026-10-13）：comment-data-ch4.json（1151 主评 + 949 回复，章评 66，60 段全有评）；sid 为本章级编号（=ugc_level3_id）；固定/内容同名标签合并（建议 34、好评 5）；sid 13/20 短对话行缺失归未匹配（2 块）；字体子集重建（898KB）；冒烟测试扩到 359 项
- [x] **ch5 剑烛大荒_小章居士接入**（2026-10-13）：comment-data-ch5.json（1539 主评 + 415 回复 + 2 孤儿，章评 106 = sid-1 67 + sid0 39；103 段 = 96 正文行 - 6 广告行 + 1 行内切分 + 6 quote 注入缺失段；80 段有评、未匹配 0）；确定性前缀锚定匹配替代五阶段模糊匹配；章末 PS 段（sid105，157 条评论）注入；字体子集重建（898KB）；冒烟测试扩到 390 项

未做 / 待定：

- [ ] 章节目录为硬编码（2026-10-13 瘦身：《没钱修什么仙》只保留第1章，未接入数据的 15 个占位章节已移除），未接真实接口
- [ ] 评论输入框 `<input class="ipt" id="cmInput">` 只有 UI，回车无行为（发布评论不在本期 PRD 范围）
- [ ] 点赞 / 回复按钮无实际逻辑（不在本期 PRD 范围）
- [ ] `#cmFilterBtn` 筛选按钮只有 toggle 视觉，未接真实筛选器 dropdown
- [ ] AI 总结卡内容是硬编码文案（PRD 未要求动态生成）
- [ ] 段评 tab（renderParagraphsOverview）还是旧布局，冒烟测试未覆盖；如需对齐 Figma 可后续迭代
- [x] 部署链路已接（2026-09-06）：GitHub Pages 服务 master 根目录，线上 https://moomin121.github.io/chapter-comments/ ，仓库 https://github.com/moomin121/chapter-comments ；本地验证后 `./publish.sh` 一键发布（冒烟测试 → commit → push → 轮询 Pages 构建完成 → curl 验证）
