#!/usr/bin/env bash
# 章节评论页冒烟测试
#
# 用法： ./test/smoke-test.sh
# 依赖： agent-browser（/opt/homebrew/bin/agent-browser）、python3
#
# 覆盖：
#   1. 数据完整性 — 190 段 / 145 气泡 / 全章评论 7293 / 段评 5744
#   2. 布局铁律   — 右侧图标栏贴 viewport 最右（抽屉开、关两种状态 gap 都必须为 0）
#   3. Figma 对齐 — 左栏、标题区、工具栏、右侧栏入口与设计稿一致
#   4. 评论面板   — 全章评论、单段段评、排序、标签云、筛选入口、原文引用
#   5. 零值段     — count 为 0 的段不渲染气泡
set -uo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT=${PORT:-8211}
URL="http://127.0.0.1:${PORT}/index.html"
BROWSER=${BROWSER:-agent-browser}

# ---------- 起静态服务器 ----------
python3 -m http.server "$PORT" --directory "$DIR" >/dev/null 2>&1 &
SERVER_PID=$!
# 收尾：kill 后用 wait 吞掉 "Terminated" 提示，避免污染测试结果输出
trap 'kill $SERVER_PID 2>/dev/null; wait $SERVER_PID 2>/dev/null; $BROWSER close >/dev/null 2>&1' EXIT
sleep 1.5

if ! curl -s -o /dev/null -w '%{http_code}' "$URL" | grep -q 200; then
  echo "FAIL: server did not start ($URL)"; exit 1
fi

# ---------- 打开页面 ----------
$BROWSER open "$URL" >/dev/null 2>&1
sleep 2

# ---------- 跑断言 ----------
# JS 里用 key 断言，输出 "状态|名称|实际|期望"，避免 JSON 转义踩坑
JS=$(cat <<'JSEOF'
(function(){
  var out = [];
  function chk(name, actual, expected){
    out.push((String(actual)===String(expected)?'PASS':'FAIL')+'|'+name+'|'+actual+'|'+expected);
  }
  var $  = function(s){ return document.querySelector(s); };
  var $$ = function(s){ return Array.prototype.slice.call(document.querySelectorAll(s)); };

  // --- 1. 数据完整性 ---
  chk('段落数', $$('.para').length, 190);
  chk('段评气泡数', $$('.para-bubble').length, 145);
  chk('全章评论数(抽屉标题)', $('#cmCount').textContent, '7293条');
  chk('抽屉标题文案', $('#cmTitleText').textContent, '评论');
  chk('段评总数', $('#chapSecTotal').textContent, 5744);
  chk('章节标题', $('#chapTitle').textContent, '第1章 面试');
  chk('发布时间', $('#chapPublishedAt').textContent, '2023-07-31 19:26');
  chk('章节类型', $('#chapVisibility').textContent, '公众章节');
  chk('标题章评胶囊隐藏', getComputedStyle($('#chapBubble')).display, 'none');

  // --- 1b. 左侧目录（Figma 稿）---
  chk('左栏分组数', $$('.lp-group').length, 2);
  chk('左栏章节项数', $$('.lp-item').length, 16);
  chk('左栏第一分组', $('.lp-group:nth-of-type(1) .nm').textContent, '作品相关');
  chk('左栏第二分组', $('.lp-group:nth-of-type(2) .nm').textContent, '正文卷');
  chk('左栏激活章节', $('.lp-item.active .nm').textContent, '第1章 面试');
  chk('左栏激活字数', $('.lp-item.active .wc').textContent, '3359');
  chk('左栏已完成章(1-6)', $$('.lp-item.done').length, 6);
  chk('左栏子章节无圆点(7-16)', $$('.lp-item.no-glyph').length, 10);
  chk('左栏带图章节(第8章)', $$('.lp-item .pic').length, 1);
  chk('左栏无残留作品选择器', !!document.querySelector('.lp-book'), false);

  // --- 1c. 顶部工具栏与右侧栏（Figma 稿）---
  chk('工具栏高度48', Math.round($('.toolbar').getBoundingClientRect().height), 48);
  chk('修改按钮文案', $('.tb-publish').textContent.trim(), '修改');
  chk('修改按钮宽度102', Math.round($('.tb-publish').getBoundingClientRect().width), 102);
  chk('专注监测隐藏', getComputedStyle($('#camPill')).display, 'none');
  chk('右侧栏评论无徽章', !!$('#rrComments .badge'), false);
  chk('右侧栏双栏在评论前', $$('.rightrail .rr-btn').map(function(el){return el.textContent.trim();}).join('>').indexOf('双栏>评论') >= 0, true);
  chk('右侧栏包含妙笔', $$('.rightrail .rr-btn').some(function(el){return el.textContent.trim()==='妙笔';}), true);

  // --- 2. 布局铁律：抽屉展开时图标栏贴右 ---
  var rail = $('.rightrail').getBoundingClientRect();
  chk('图标栏贴右(抽屉开)', Math.round(innerWidth - rail.right), 0);
  chk('评论抽屉宽度320', Math.round($('#cmDrawer').getBoundingClientRect().width), 320);

  // --- 3. 零值段不渲染气泡（第 5 段 / idx=4 是零值段）---
  chk('零值段无气泡(idx4)', !!$('.para[data-idx="4"] .para-bubble'), false);
  chk('非零值段有气泡(idx17)', !!$('.para[data-idx="17"] .para-bubble'), true);

  // --- 4. 交互：点击截图里的第 3 段气泡 ---
  $('.para-bubble[data-idx="2"]').click();
  var act = $('.para.active');
  chk('点击气泡后高亮段', act ? act.dataset.idx : 'none', 2);
  chk('抽屉切段评视图', $('#cmDrawer').classList.contains('parasec'), true);
  chk('段评抽屉标题', $('#cmTitleText').textContent, '评论');
  chk('段评抽屉计数', $('#cmCount').textContent, '2条');
  chk('段评视图隐藏标签', getComputedStyle($('#cmTags')).display, 'none');
  chk('段评引用区可见', getComputedStyle($('#cmContext')).display, 'block');
  chk('段评视图保留排序', getComputedStyle($('#cmSort')).display, 'flex');
  chk('工具栏返回按钮隐藏', getComputedStyle($('#cmBack')).display, 'none');
  chk('工具栏更多按钮存在', !!$('#cmMoreBtn'), true);
  chk('段评视图隐藏输入框', getComputedStyle($('.cm-input')).display, 'none');
  chk('段评标题栏高度42', Math.round($('.cm-hd').getBoundingClientRect().height), 42);
  chk('段评排序栏高度32', Math.round($('.cm-toolbar').getBoundingClientRect().height), 32);
  chk('段评不显示段落标题', ($('.cm-list').textContent||'').indexOf('第3段') >= 0, false);
  chk('段评引用原文', ($('.cm-section-module.single .cm-quote').textContent||'').indexOf('手术费') >= 0, true);
  chk('引用条返回入口', !!$('.cm-quote-back'), true);
  chk('段评首条内容', ($('.cm-list > .cm-item .content').textContent||'').indexOf('387.6') >= 0, true);
  chk('段评列表首项为评论', $('.cm-list > :first-child').classList.contains('paragraph-comment'), true);
  chk('段评视图无章评', $$('.cm-list > .chapter-comment').length, 0);
  chk('段评只显示2条', $$('.cm-list > .paragraph-comment').length, 2);
  chk('段评含UGC图占位', !!$('.paragraph-comment .cm-ugc'), true);
  chk('段评元信息左右布局', getComputedStyle($('.paragraph-comment .meta')).justifyContent, 'space-between');
  chk('段评元信息右侧操作', !!$('.paragraph-comment .cm-meta-actions'), true);
  chk('选中段浅红背景', getComputedStyle(act).backgroundImage.indexOf('255, 121, 80') >= 0, true);
  chk('右侧评论Tab蓝线', getComputedStyle($('#rrComments'), '::before').width, '2px');
  $('#cmSortHot').click();
  chk('段评内排序不退出', $('#cmDrawer').classList.contains('parasec'), true);

  // --- 5. 评论面板：排序、标签云、筛选入口、一级评论引用 ---
  $('.cm-quote-back').click();
  chk('返回后抽屉标题', $('#cmTitleText').textContent, '评论');
  chk('返回后抽屉计数', $('#cmCount').textContent, '7293条');
  chk('全章统计说明隐藏', !!$('.cm-overview'), false);
  chk('全章段评模块不展示', $$('.cm-section-module:not(.single)').length, 0);
  chk('全章AI总结卡存在', !!$('.cm-ai-card'), true);
  chk('全章列表首项为AI总结', $('.cm-list > :first-child').classList.contains('cm-ai-card'), true);
  chk('全章引用条存在', !!$('.cm-reference'), true);
  chk('全章引用条含气泡', $('.cm-ref-bubble').textContent.trim(), '2');
  chk('全章评论项数', $$('.cm-list > .full-comment').length, 6);
  chk('全章评论都有操作行', $$('.cm-list > .full-comment .cm-meta-actions').length, 6);
  chk('全章标签可见', getComputedStyle($('#cmTags')).display, 'flex');
  chk('排序项', $$('#cmSort .cm-tab').map(function(el){return el.textContent.trim();}).join('/'), '默认/最热/最新');
  chk('最热排序保持选中', $('#cmSortHot').classList.contains('on'), true);
  chk('筛选按钮存在', !!$('#cmFilterBtn'), true);
  chk('筛选按钮在右侧', $('#cmFilterBtn').getBoundingClientRect().left > $('#cmSort').getBoundingClientRect().right, true);
  chk('标签云数量', $$('.cm-tag').length, 18);
  chk('标签云内容', $$('.cm-tag').map(function(el){return el.textContent.trim();}).join('|'), '全部 7293|👍🏻好评 113|🍅差评 12|💡建议 10|❓疑问 3|👈🏻提及作者 133|📚提及其他作品 111|🍚️二创 61|⭐️建议加精 69|🚫建议屏蔽 10|现实/太真实 401|太颠/太抽象/太离谱 343|笑死/绷不住 140|好惨/心痛/压抑 116|资本修仙/赛博朋克 320|面试像找工作/太卷 205|不睡觉太狠 231|绝育/变性/器官改造太狠 200');
  chk('标签云默认全部', $('.cm-tag.on').textContent.trim(), '全部 7293');
  chk('标签高度改小', Math.round($('.cm-tag').getBoundingClientRect().height), 22);
  chk('标签字号改小', getComputedStyle($('.cm-tag')).fontSize, '12px');
  chk('标签无气泡尾巴', getComputedStyle($('.cm-tag.on'), '::after').content, 'none');
  var tagOrderBeforeClick = $$('.cm-tag').map(function(el){return el.textContent.trim();}).join('|');
  $$('.cm-tag').find(function(el){ return el.textContent.trim() === '现实/太真实 401'; }).click();
  chk('可切换当前标签', $('.cm-tag.on').textContent.trim(), '现实/太真实 401');
  chk('选中后标签顺序固定', $$('.cm-tag').map(function(el){return el.textContent.trim();}).join('|'), tagOrderBeforeClick);
  $('#cmList').scrollTop = 90;
  $('#cmList').dispatchEvent(new Event('scroll'));
  chk('滚动后标签折叠', $('#cmTags').classList.contains('collapsed'), true);
  chk('折叠后保持一行高度', Math.round($('#cmTags').getBoundingClientRect().height) <= 42, true);
  var listTopBeforeHover = Math.round($('#cmList').getBoundingClientRect().top);
  var listScrollBeforeHover = $('#cmList').scrollTop;
  $('#cmTags').dispatchEvent(new Event('mouseenter'));
  chk('hover标签行展开', $('#cmTags').classList.contains('hover-open'), true);
  chk('hover不改变列表顶部', Math.round($('#cmList').getBoundingClientRect().top), listTopBeforeHover);
  chk('hover不改变列表滚动值', $('#cmList').scrollTop, listScrollBeforeHover);
  $('#cmTags').dispatchEvent(new Event('mouseleave'));
  chk('离开标签行收起', $('#cmTags').classList.contains('hover-open'), false);
  chk('全章一级评论数量', $$('.cm-list > .full-comment').length, 6);
  chk('AI总结含去提问', $('.cm-ai-ask').textContent.trim(), '去提问 >');
  chk('全章引用最多一行', Math.round($('.cm-reference').getBoundingClientRect().height), 36);
  $('#cmSortHot').click();
  chk('最热排序选中', $('#cmSortHot').classList.contains('on'), true);
  chk('最热首条点赞最高', $('.cm-list > .full-comment .cm-meta-actions').textContent.indexOf('2872') >= 0, true);
  $('#cmSortLatest').click();
  chk('最新排序选中', $('#cmSortLatest').classList.contains('on'), true);
  chk('最新首条为最新日期', $('.cm-list > .full-comment .cm-meta-left').textContent.indexOf('05月09日 22:41') >= 0, true);
  $('#cmFilterBtn').click();
  chk('筛选按钮可激活', $('#cmFilterBtn').classList.contains('on'), true);

  // --- 6. 布局铁律：抽屉折叠后图标栏依然贴右 ---
  $('#cmClose').click();
  var rail2 = $('.rightrail').getBoundingClientRect();
  chk('图标栏贴右(抽屉关)', Math.round(innerWidth - rail2.right), 0);

  // --- 6b. 段落首行缩进（无论 comment-mode 都生效；font-size 20px × 2em = 40px）---
  chk('首段缩进(2em)', getComputedStyle($('.para')).textIndent, '40px');
  chk('对话段也缩进', getComputedStyle($('.para.dialog')).textIndent, '40px');

  // --- 7. 评论模式开关（toggle）：关闭后正文仍可见、气泡/抽屉/讨论热词/章评都隐藏 ---
  // 此时 comment-mode 应为 false（cmClose 已关闭）
  chk('评论按钮不再激活', $('#rrComments').classList.contains('active'), false);
  chk('正文仍可见(关闭)', getComputedStyle($('.para')).display, 'block');
  chk('段评气泡隐藏(关闭)', getComputedStyle($('.para-bubble')).display, 'none');
  chk('讨论热词隐藏(关闭)', getComputedStyle($('.chap-meta')).display, 'none');
  chk('章评胶囊隐藏(关闭)', getComputedStyle($('#chapBubble')).display, 'none');
  chk('抽屉宽度为0(关闭)', Math.round($('#cmDrawer').getBoundingClientRect().width), 0);

  // 再次点 #rrComments → 重新开启，全部恢复
  $('#rrComments').click();
  chk('评论模式重开', document.body.classList.contains('comment-mode'), true);
  chk('评论按钮重新激活', $('#rrComments').classList.contains('active'), true);
  chk('段评气泡重新显示', getComputedStyle($('.para-bubble')).display, 'inline-flex');
  chk('讨论热词保持隐藏', getComputedStyle($('.chap-meta')).display, 'none');
  chk('抽屉展开', $('#cmDrawer').classList.contains('open'), true);

  // --- 8. 评论模式下气泡采用正文参考图的小描边角标，并保持数字居中 ---
  var bubbleOne = $('.para[data-idx="6"] .para-bubble');
  var bubbleThree = $('.para[data-idx="0"] .para-bubble');
  var bubbleGrey = $('.para[data-idx="6"] .para-bubble');
  chk('气泡1位数最小宽度', Math.round(bubbleOne.getBoundingClientRect().width), 18);
  chk('气泡3位数自适应更宽', Math.round(bubbleThree.getBoundingClientRect().width) > Math.round(bubbleOne.getBoundingClientRect().width), true);
  chk('气泡白色底', getComputedStyle(bubbleThree).backgroundColor.indexOf('255, 255, 255') >= 0, true);
  chk('高热气泡红色描边', getComputedStyle(bubbleThree).borderTopColor, 'rgb(255, 59, 79)');
  chk('低热气泡灰色描边', getComputedStyle(bubbleGrey).borderTopColor, 'rgb(111, 115, 122)');
  // 气泡内数字垂直居中：上边距 == 下边距（差异 ≤ 1px）
  var bubble0 = $('.para-bubble');
  var rb = bubble0.getBoundingClientRect();
  var rangeB = document.createRange(); rangeB.selectNodeContents(bubble0);
  var rt = rangeB.getBoundingClientRect();
  var topGap = Math.round(rt.top - rb.top);
  var botGap = Math.round(rb.bottom - rt.bottom);
  chk('气泡文字垂直居中(差≤1)', Math.abs(topGap - botGap) <= 1, true);
  var leftGap = Math.round(rt.left - rb.left);
  var rightGap = Math.round(rb.right - rt.right);
  chk('气泡文字水平居中(差≤1)', Math.abs(leftGap - rightGap) <= 1, true);

  // --- 9. 全章评论流布局对齐 Figma 稿 ---
  var fullFirst = $('.cm-list > .full-comment');
  chk('全章评论头像28px', Math.round(fullFirst.querySelector('.av').getBoundingClientRect().width), 28);
  chk('全章评论正文14px', getComputedStyle(fullFirst.querySelector('.content')).fontSize, '14px');
  chk('全章评论含UGC图', !!fullFirst.querySelector('.cm-ugc'), true);
  chk('全章评论元信息含楼层', fullFirst.querySelector('.cm-meta-left').textContent.indexOf('1楼 ·') >= 0, true);
  chk('全章评论元信息中文日期', fullFirst.querySelector('.cm-meta-left').textContent.indexOf('月') >= 0, true);
  chk('全章评论操作图标20px', Math.round(fullFirst.querySelector('.cm-meta-actions svg').getBoundingClientRect().width), 20);
  chk('全章评论操作间距12px', getComputedStyle(fullFirst.querySelector('.cm-meta-actions')).columnGap, '12px');
  chk('全章回复入口存在', !!fullFirst.querySelector('.cm-more-replies'), true);
  chk('全章到底文案', $('.cm-empty').textContent.trim(), '-到底了-');

  return out.join('\n');
})()
JSEOF
)

RESULT=$($BROWSER eval "$JS" 2>&1 | tail -n +1)

# agent-browser 可能把结果包在一层引号里，去掉首尾引号与转义
RESULT=$(printf '%s' "$RESULT" | sed -e 's/^"//' -e 's/"$//' -e 's/\\n/\n/g' -e 's/\\"/"/g')

# ---------- 输出结果 ----------
PASS=0; FAIL=0
echo "──────── 章节评论页冒烟测试 ────────"
while IFS='|' read -r status name actual expected; do
  [ -z "${status:-}" ] && continue
  case "$status" in
    PASS) printf '  ✓ %-24s %s\n' "$name" "$actual"; PASS=$((PASS+1));;
    FAIL) printf '  ✗ %-24s 实际=%s 期望=%s\n' "$name" "$actual" "$expected"; FAIL=$((FAIL+1));;
  esac
done <<< "$RESULT"
echo "───────────────────────────────────"
echo "  通过 $PASS 项，失败 $FAIL 项"
[ "$FAIL" -eq 0 ] || exit 1
