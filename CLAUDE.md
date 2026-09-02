# CLAUDE.md — 章节评论页 · Codex 上下文

> 这是给 Codex / Claude Code / WorkBuddy 等 AI 工具读的项目说明。人类开发者请看 [README.md](README.md)。

## 项目一句话总结

单文件网页 `index.html`，起点风格的小说章节阅读页 + 段评气泡 + 评论抽屉。HTML + CSS + JS 全部内联。71KB。190 段示例章节正文 + 145 个段评气泡。

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

### 2. 段评数字必须准确，不能编造

需求原话：「评论数字要对」。

所有数字来自起点章节页截图的 OCR，经过**三轮交叉验证**（原尺寸识别 → sips 放大 2× 再识别 → 裁剪气泡区域放大 10× 只认数字）。仍然有 45 段识别不到，兜底设为 0（不显示气泡）。

**不要为了"让每段都有气泡"而编数字**。用户如果发现哪段该有数字却没显示，让他报段号，改 `SECTION_COUNTS` 对应下标即可（清单见下方「零值段清单」）。

### 3. 不要拆分为多文件

单文件是刻意的，为了 Codex / WorkBuddy 用 diff 协作。见「不要做的修改」。

## 技术栈

- **纯原生**：HTML + CSS + 原生 JS（无构建步骤、无依赖、无打包）
- **字体**：LXGW WenKai（jsdelivr CDN `<link rel="preconnect">` + `@font-face`）
- **数据**：内置在 `var CHAPTER = {...}` 中
- **存储**：`localStorage.wb_comment_mode` 记忆评论开关（默认开启，可忽略）

## 文件边界

```
chapter-comments/index.html        # 唯一源文件（约 12100 行，含大量空行/注释）
chapter-comments/CLAUDE.md         # 本文件
chapter-comments/README.md         # 人类开发文档
```

**不要试图拆分 index.html**：单文件设计便于 diff 和热重载，协作时请保持原样。

## 关键代码定位（用注释关键字搜索）

以下注释在 `index.html` 里都唯一，定位用 grep 即可：

| 注释关键字 | 作用 |
|---|---|
| `/* ============ 章节阅读视图（含段评气泡 / 评论抽屉） ============ */` | 段评气泡 + 评论抽屉 CSS 起始 |
| `.cm-drawer{` | 评论抽屉容器 CSS |
| `// 0) 示例章节：` | CHAPTER 数据块起始 |
| `// 1) 工具` | `$(s)` / `$$(s)` / `escapeHtml` / `heatClass` / `avatarColor` 工具函数 |
| `// 2) 渲染 reader` | `renderReader()` 渲染段落 + 气泡 |
| `// 3) 段选择联动` | `selectParagraph(idx)` 点击气泡 → 高亮 + 切抽屉 |
| `// 4) 渲染段评列表` | `renderParagraphComments(idx)` 单段段评视图 |
| `// 5) 渲染全部评论` | `renderAllComments()` 章评主楼 + 楼中楼 |
| `// 6) 段评 tab` | `renderParagraphsOverview()` 段评导航 |
| `// 7) 模式控制：评论模式开关` | `setCommentMode(on)` / `switchCmTab(name)` |
| `// 8) 初始化 + 事件绑定` | `init()` |

## 数据契约

```js
var CHAPTER = {
  title: '...',                    // 章节标题
  meta: {work, author, words, time},
  chapterCommentCount: 621,        // 章评数（标题旁胶囊、抽屉标题、右栏徽章）
  paragraphs: ['段1', '段2', ...]  // 190 段
};
var SECTION_COUNTS = [105, 21, ...];  // 190 个数字，与 paragraphs 一一对应
```

- 改章节数据：同步改 `paragraphs` 和 `SECTION_COUNTS`，长度必须一致
- 改段评数显示位置：`getParagraphs()` / `renderReader()` 末尾的 DOM 更新

## 不要做的修改

1. **不要改 `function $(s)` 的实现** — 是大量脚本的全局工具函数，改名会牵动 50+ 处调用
2. **不要把内联 CSS 拆出去** — 保持单文件，便于 Codex/WorkBuddy 用 diff 协作
3. **不要引入新依赖**（jQuery、Vue、Tailwind 等）— 当前是纯原生架构，加依赖会把单文件变成构建项目

## 加新功能时的模式

例如「在评论抽屉顶部加个「只看我的关注」开关」：

1. **DOM**：在 `<aside class="cm-drawer" id="cmDrawer">` 里 `<div class="cm-toolbar">` 旁边加一个 `<div class="cm-follow-toggle">`
2. **CSS**：在 `.cm-toolbar{...}` 附近加 `.cm-follow-toggle{...}`
3. **JS**：在 `// 7) 模式控制：评论模式开关` 附近加 `function toggleFollowOnly(){...}`，并在 `renderAllComments` / `renderParagraphComments` 里调用时检查状态

始终遵循：**数据契约不变 → 渲染函数增加过滤条件 → 不破坏现有 DOM 结构**。

## 已知 OCR 残留风险：零值段清单

CHAPTER 数据来自起点章节页截图，OCR **三轮交叉验证**后仍有 45 段识别不出数字，兜底设为 `0`（不渲染气泡）。

**零值段号（1-based，共 45 个）**：

```
5, 26, 37, 57, 62, 65, 66, 69, 74, 86, 89, 96, 99, 104, 106, 107, 108, 109,
115, 118, 119, 121, 126, 131, 135, 137, 140, 143, 144, 149, 150, 152, 154,
155, 156, 159, 160, 161, 166, 171, 172, 178, 180, 185, 186
```

这些段多为短句、纯对话或省略号（如第 5 段「良久之后，前方传来一阵叫号声。」、第 66 段「"哼。"」），气泡小、对比度低，OCR 漏识率高。

若用户报「第 N 段应该有数字但没显示」：
1. 确认 N 在上面的清单里
2. 改 `SECTION_COUNTS[N-1]` 即可（下标 = 段号 - 1）
3. 顺手更新本清单，把该段号移除

**不要**批量把 0 改成非零——那等于编造数据。

## 当前数据快照

```
段落数        190
有气泡的段     145
无气泡的段      45
段评总数      5744
章评数        621
作品名        没钱修什么仙？
作者          熊狼狗
章节标题      第1章 面试
字数          6016
```

热度 Top 5 段（可用来做视觉回归的锚点）：

| 段号 | 段评数 | 颜色档位 |
|---|---|---|
| 第 27 段 | 366 | 深红 |
| 第 60 段 | 278 | 深红 |
| 第 40 段 | 268 | 深红 |
| 第 18 段 | 257 | 深红 |
| 第 132 段 | 253 | 深红 |

## 测试入口

- `index.html`：默认直接进入评论模式（阅读视图 + 抽屉自动展开）
- `index.html?cm=para-17`：跳到第 18 段（257 条段评，**最高热度之一**），可一次验证：气泡深红档、段落高亮、抽屉切段评视图、楼中楼展开
- `index.html?cm=para-19`：跳到第 20 段（21 条段评，长段落换行场景）
- `index.html?cm=para-4`：跳到第 5 段（**零值段**，不该有气泡，用来验证 0 值不渲染）

> 注意：旧文档里写的「para-19 = 14 条段评」是上一版示例数据，已过时。

## 验证方法

**改完一定要跑像素探针，不要只截图看**：

```bash
# 起服务
cd /Users/moomin/WorkBuddy/编辑器 && python3 server.py 8210

# 打开页面
agent-browser open "http://127.0.0.1:8210/chapter-comments/index.html"
```

然后用 `agent-browser eval` 做断言式检查：

```js
// 1) 数据完整性
document.querySelectorAll('.para').length        // 应为 190
document.querySelectorAll('.para-bubble').length // 应为 145

// 2) 布局铁律（抽屉开关两种状态都要 0）
var r = document.querySelector('.rightrail').getBoundingClientRect();
innerWidth - r.right                             // 应为 0

// 3) 交互
document.querySelector('.para-bubble[data-idx="17"]').click();
document.querySelector('.para.active').dataset.idx  // 应为 "17"
```

`.para-bubble[data-idx="17"]` 这类选择器在 shell 里引号容易冲突，建议用 `eval` + 转义双引号，或直接用 `?cm=para-N` URL 参数，更可靠。

## 交接状态（截至 2026-09-02）

已完成：

- [x] 从 `write.html`（1.3MB 混合体）拆出为独立页面，去掉 1.25MB base64 视频和专注监测逻辑
- [x] 正文替换为《没钱修什么仙？》第 1 章，190 段 + 段评数（OCR 三轮交叉验证）
- [x] 段评气泡 5 档热力色阶
- [x] 点击气泡 → 段落高亮 + 抽屉切段评视图
- [x] 段评 tab（按热度列出全部 190 段，点击跳转）
- [x] 章评主楼 + 楼中楼展开/收起
- [x] 右侧图标栏永久贴最右（flex order 修正）
- [x] git 仓库初始化，首次提交 `df3d5ac`

未做 / 待定：

- [ ] 45 个零值段的数字待用户肉眼核对
- [ ] 章节列表是硬编码 16 章，未接真实接口
- [ ] 评论输入框 `<input class="ipt" id="cmInput">` 只有 UI，回车无行为
- [ ] 点赞 / 回复按钮无实际逻辑
- [ ] 未接真实评论数据接口（当前评论内容来自内置 `SECTION_POOL` 循环复用）
- [ ] 部署链路未接（gh-pages 子目录 / Vercel / CloudStudio 待定）