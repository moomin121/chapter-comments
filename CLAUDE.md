# CLAUDE.md — 章节评论页 · Codex 上下文

> 这是给 Codex / Claude Code / WorkBuddy 等 AI 工具读的项目说明。人类开发者请看 [README.md](README.md)。

## 项目一句话总结

单文件网页 `index.html`，起点风格的小说章节阅读页 + 段评气泡 + 评论抽屉。HTML + CSS + JS 全部内联。71KB。190 段示例章节正文 + 145 个段评气泡。

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

## 已知 OCR 残留风险

CHAPTER 数据来自起点章节页截图（OCR 三轮交叉验证）。约 45 段被设为 0（无气泡），可能实际有 1~2 位小数字被 OCR 漏识。如果用户报"某段应该有数字但没显示"，在 OCR 校对表（项目根 `.workbuddy/memory/2026-09-02.md` 第六轮）里查对应段号，修正后只需改 `SECTION_COUNTS` 对应下标。

## 测试入口

- `index.html`：默认直接进入评论模式
- `index.html?cm=para-19`：直接跳到第 20 段（"公交账..."，14 条段评），可验证段评跳转 + 抽屉切换 + 楼中楼
- `index.html?debug=bark`：专注监测页用，本页不生效