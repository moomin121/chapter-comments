#!/usr/bin/env bash
# 章节评论页冒烟测试 v2 —— 按 PRD §16 验收标准重写
#
# 用法： ./test/smoke-test.sh
# 依赖： agent-browser（/opt/homebrew/bin/agent-browser）、python3
#
# 两段断言：
#   A. 数据预处理 —— CSV → COMMENT_DATA 统计校验（不依赖浏览器）
#   B. 页面渲染 —— PRD §16 十二条验收的浏览器断言
#
# ⚠️ 断言锚点是当前 CSV 数据快照（4465 一级 / 3028 回复 / 172 有评段 /
#    章评 621 / 段评 6209）。CSV 更新后需同步改锚点并重新生成数据块。
set -uo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT=${PORT:-8211}
URL="http://127.0.0.1:${PORT}/index.html"
BROWSER=${BROWSER:-agent-browser}

# ---------- A. 数据预处理校验 ----------
CSV_PATH="/Users/moomin/Documents/ChatGPT/New project/outputs/who_made_him_cultivate_ch1_comments/谁让他修仙的第1章评论_作者视角打标.csv"
if [ ! -f "$CSV_PATH" ]; then
  echo "SKIP: CSV 不存在，跳过数据段校验（$CSV_PATH）"
else
  BUILD_OUT=$(python3 "$DIR/scripts/build_comment_data.py" 2>/dev/null | tail -1)
  echo "build: $BUILD_OUT"
  echo "$BUILD_OUT" | grep -q "4465 main, 2365 replies, 171 paragraph targets, 663 orphan replies" \
    || { echo "FAIL: 数据预处理统计不符"; exit 1; }
  # 生成的数据块必须已在 index.html 里（比较生成区与落盘区一致）
  python3 - "$DIR/scripts/build_comment_data.py" "$DIR/index.html" <<'PYEOF'
import re, subprocess, sys, pathlib
script = pathlib.Path(sys.argv[1]); index = pathlib.Path(sys.argv[2])
out = subprocess.run(["python3", str(script)], capture_output=True, text=True).stdout
block = re.search(r"// GENERATED_COMMENT_DATA_START.*?// GENERATED_COMMENT_DATA_END", out, re.S)
cur = re.search(r"// GENERATED_COMMENT_DATA_START.*?// GENERATED_COMMENT_DATA_END",
                index.read_text(encoding="utf-8"), re.S)
if not block or not cur:
    sys.exit("FAIL: 找不到生成数据块")
if block.group(0) != cur.group(0):
    sys.exit("FAIL: index.html 内联数据块与 CSV 最新构建不一致，请跑 build_comment_data.py --update-index")
PYEOF
  [ $? -eq 0 ] || exit 1
fi

# ---------- 起静态服务器 ----------
python3 -m http.server "$PORT" --directory "$DIR" >/dev/null 2>&1 &
SERVER_PID=$!
trap 'kill $SERVER_PID 2>/dev/null; wait $SERVER_PID 2>/dev/null; $BROWSER close >/dev/null 2>&1' EXIT
sleep 1.5

if ! curl -s -o /dev/null -w '%{http_code}' "$URL" | grep -q 200; then
  echo "FAIL: server did not start ($URL)"; exit 1
fi

# ---------- 打开页面 ----------
$BROWSER open "$URL" >/dev/null 2>&1
sleep 4

# ---------- B. 页面渲染断言 ----------
# JS 里用 key 断言，输出 "状态|名称|实际|期望"
JS=$(cat <<'JSEOF'
(function(){
  var out = [];
  function chk(name, actual, expected){
    out.push((String(actual)===String(expected)?'PASS':'FAIL')+'|'+name+'|'+actual+'|'+expected);
  }
  var $  = function(s){ return document.querySelector(s); };
  var $$ = function(s){ return Array.prototype.slice.call(document.querySelectorAll(s)); };

  // --- §16-1 默认展开评论侧边栏 + 全部评论视图 ---
  chk('抽屉默认展开', $('#cmDrawer').classList.contains('open'), true);
  chk('默认全部评论视图', !$('#cmDrawer').classList.contains('parasec'), true);
  chk('有效评论总数(732+6098)', $('#cmCount').textContent, '6830条');

  // --- §16-2 气泡：真实计数 / 0 不显示 / 标题胶囊 ---
  chk('段落数', $$('.para').length, 190);
  chk('有评段气泡数', $$('.para-bubble').length, 170);
  chk('标题章评胶囊显示', getComputedStyle($('#chapBubble')).display, 'flex');
  chk('标题章评数', $('#chapBubble').textContent, '732');
  chk('标题气泡复用热度样式', $('#chapBubble').classList.contains('lv-red'), true);
  chk('标题气泡与段泡同高', getComputedStyle($('#chapBubble')).height, getComputedStyle($('.para-bubble')).height);
  chk('标题气泡使用描边', getComputedStyle($('#chapBubble')).borderTopWidth, '1px');
  chk('段评总数', $('#chapSecTotal').textContent, '6098');
  chk('章评聚合计数(气泡最后一块)', $$('.cm-reference[data-target-id="-1"] .cm-ref-bubble')[0].textContent, '732');

  // --- §16-4 全部评论：AI 卡置顶 + 章节标题评论在首段之前 + 未匹配兜底 ---
  chk('AI总结卡存在', $$('.cm-ai-card').length, 1);
  chk('AI总结卡是首项', $('#cmList > :first-child').classList.contains('cm-ai-card'), true);
  // AI 卡默认收起 3 行（Figma 88-9492）；点击【展开全部】展开且按钮消失（Figma 97-14607）
  chk('AI卡默认收起', !!$('.cm-ai-body.clamped'), true);
  chk('AI卡收起高度60', getComputedStyle($('.cm-ai-body')).maxHeight, '60px');
  chk('AI卡有展开按钮', !!$('.cm-ai-expand'), true);
  $('.cm-ai-expand').click();
  chk('AI卡展开后无裁切', !!$('.cm-ai-body.clamped'), false);
  chk('AI卡展开后无按钮', !!$('.cm-ai-expand'), false);
  chk('AI卡展开高度超3行', $('.cm-ai-body').getBoundingClientRect().height > 60, true);
  chk('聚合块总数(170段+1章评+1未匹配)', $$('.cm-full-module').length, 172);
  var modules = $$('.cm-full-module');
  chk('章节标题评论存在', !!$('.cm-full-module[data-target-id="-1"]'), true);
  chk('章节标题评论在首段之前', modules[0].getAttribute('data-target-id'), '-1');
  chk('首段评论块紧随章评', modules[1].getAttribute('data-target-id'), '0');
  chk('未匹配块数(CSV越界段191)', $$('.cm-unmatched-module').length, 1);
  chk('未匹配块排在最后', modules[modules.length-1].classList.contains('cm-unmatched-module'), true);

  // --- §16-5 每段最多 3 条一级评论 + 查看本段入口 ---
  var overThree = $$('.cm-full-module').filter(function(m){
    var link = m.querySelector('.cm-section-link');
    return link && !link.closest('.cm-unmatched-module');
  });
  chk('超过3条的段有查看入口', overThree.length > 100, true);
  var firstModule = $('.cm-full-module[data-target-id]:not(.cm-unmatched-module)');
  var shown = firstModule ? firstModule.querySelectorAll(':scope > .full-comment').length : 0;
  chk('首段块展示前3条', shown <= 3, true);

  // --- §16-7 评论卡片：对象/头像/昵称/正文/回复入口 ---
  var fc = $('.cm-full-module .full-comment');
  chk('评论有头像', !!fc.querySelector('.av'), true);
  chk('评论有昵称', fc.querySelector('.nm').textContent.length > 0, true);
  chk('评论有正文', fc.querySelector('.content').textContent.length > 0, true);
  chk('评论正文字号14', getComputedStyle(fc.querySelector('.content')).fontSize, '14px');
  chk('有回复的评论有展开入口', $$('.sub-toggle').length > 100, true);
  chk('楼中楼默认收起', $$('.cm-sub[style*="display: none"], .cm-sub[style*="display:none"]').length === $$('.cm-sub').length, true);
  // --- 需求6 评论底部操作：日期 + IP地址 + 评论 + 点赞"赞" + 点赞数 + ··· ---
  var metaLeft = fc.querySelector('.cm-meta-left').textContent;
  chk('评论底部含日期', /月.*日/.test(metaLeft), true);
  chk('评论底部含IP地址', metaLeft.indexOf('IP地址') >= 0, true);
  chk('点赞无赞字', fc.querySelector('.cm-meta-like b'), null);
  chk('点赞数字在按钮内', (fc.querySelector('.cm-meta-like .cm-meta-like-count')||{parentElement:{className:''}}).parentElement.className.indexOf('cm-meta-like') >= 0, true);
  chk('评论底部含更多', !!fc.querySelector('.cm-meta-more svg'), true);
  chk('更多为Figma三点', fc.querySelector('.cm-meta-more svg').getAttribute('viewBox'), '0 0 20 20');
  chk('评论按钮为Figma评论', !!fc.querySelector('.cm-meta-comment svg path'), true);
  chk('点赞按钮为Figma拇指', !!fc.querySelector('.cm-meta-like svg path'), true);

  // --- §16-3 点击段气泡 → 单对象视图全部一级评论 ---
  $('#cmList').scrollTop = 200;
  $('.para-bubble[data-idx="17"]').click();
  chk('单对象视图列表自动滚到顶', $('#cmList').scrollTop, 0);
  chk('单对象视图态', $('#cmDrawer').classList.contains('parasec'), true);
  chk('段17计数(一级+回复)', $('#cmCount').textContent, '257条');
  chk('段17全部一级评论', $$('.cm-list > .paragraph-comment').length, 193);
  // 零赞评论只显示图标、不显示数字（Figma：数字=0 仅图标）
  var zeroLike = $$('.cm-list .cm-meta-like').filter(function(el){ return !el.querySelector('.cm-meta-like-count'); });
  chk('零赞仅图标无数字', zeroLike.length > 0, true);
  chk('段17高亮', ($('.para.active')||{dataset:{}}).dataset.idx, '17');
  chk('返回全部评论按钮', !!$('.cm-quote-back'), true);
  // 楼中楼展开/收起
  var tg = $('.cm-list .sub-toggle');
  if(tg){
    tg.click();
chk('楼中楼展开', tg.parentElement.querySelector('.cm-sub').style.display !== 'none', true);
  // 二级评论头像应与一级评论昵称同列对齐（Figma 80-44007 Reply 在父 Body 内，左对齐到父 nickname）
  var replyAv = tg.parentElement.querySelector('.cm-sub .cm-item .av');
  var parNm = tg.parentElement.querySelector('.nm');
  if(replyAv && parNm){
    var diff = Math.abs(replyAv.getBoundingClientRect().left - parNm.getBoundingClientRect().left);
    chk('二级评论对齐一级昵称', diff <= 6, true);
  } else { chk('二级评论对齐一级昵称', '?', 'skip'); }
  tg.click();
    chk('楼中楼再收起', tg.parentElement.querySelector('.cm-sub').style.display === 'none', true);
  }
  // 返回全部评论
  $('.cm-quote-back').click();
  chk('返回后聚合视图', $$('.cm-full-module').length, 172);
  // 返回后恢复进入单对象视图前的滚动位置（200），而不是跳到顶部
  chk('返回后恢复原滚动位置', $('#cmList').scrollTop, 200);
  chk('返回后计数', $('#cmCount').textContent, '6830条');

  // --- §16-10/11 标签真实筛选 ---
  var tagReal = $$('.cm-tag').filter(function(t){ return t.getAttribute('data-tag') === '这不就是现实/网贷还债太真实'; })[0];
  chk('真实内容标签存在', !!tagReal, true);
  // 标签云以截图/Codex 交接版本为准：自然宽度胶囊流式换行，不使用等宽网格或长标签强制跨行。
  var tagsStyle = getComputedStyle($('#cmTags'));
  chk('标签云使用流式换行', tagsStyle.display, 'flex');
  chk('标签云允许自然换行', tagsStyle.flexWrap, 'wrap');
  chk('标签没有长标签特例', $$('.cm-tag-long').length, 0);
  chk('截图标签采用短名称', $$('.cm-tag-label').map(function(el){ return el.textContent; }).indexOf('📚 提及其他作品') >= 0, true);
  chk('建议加精短名称', $$('.cm-tag-label').map(function(el){ return el.textContent; }).indexOf('⭐ 建议加精') >= 0, true);
  chk('表格长标签不直接展示', $$('.cm-tag-label').map(function(el){ return el.textContent; }).indexOf('明确提及其他书籍/作者/其他领域的作品如游戏影视') < 0, true);
  chk('标签胶囊紧凑高度', getComputedStyle($('.cm-tag')).height, '20px');
  chk('标签字号与截图一致', getComputedStyle($('.cm-tag')).fontSize, '11px');
  chk('标签间距紧凑', getComputedStyle($('#cmTags')).gap, '6px');
  // 列表滚动后标签会收起；悬停应按内容完整展开，不能固定 194px 裁切末行。
  $('#cmList').scrollTop = 80;
  $('#cmList').dispatchEvent(new Event('scroll'));
  $('#cmTags').dispatchEvent(new Event('mouseenter'));
  var tagBox = $('#cmTags').getBoundingClientRect();
  var tagLabels = $$('#cmTags .cm-tag-label');
  var lastTag = tagLabels[tagLabels.length - 1];
  chk('悬停标签区完整展开', $('#cmTags').classList.contains('hover-open'), true);
  chk('悬停标签区高度充足', $('#cmTags').getBoundingClientRect().height > 34, true);
  chk('悬停末行标签未裁切', lastTag.getBoundingClientRect().bottom <= tagBox.bottom + 1, true);
  $('#cmTags').dispatchEvent(new Event('mouseleave'));
  if(tagReal){
    tagReal.click();
    chk('标签选中态', $('.cm-tag.on').getAttribute('data-tag'), '这不就是现实/网贷还债太真实');
    chk('筛选后聚合块变少', $$('.cm-full-module').length < 172, true);
    chk('筛选后仍按段聚合', $$('.cm-full-module').length > 50, true);
    // 筛选后应自动滚到列表顶部（scrolled-to-top 等价于 list.scrollTop === 0）
    chk('筛选后自动滚到顶', $('#cmList').scrollTop, 0);
    // 筛选后不应再显示 AI 卡
    chk('筛选后隐藏AI卡', $$('.cm-ai-card').length, 0);
    var tagAll = $$('.cm-tag').filter(function(t){ return t.getAttribute('data-tag') === '全部'; })[0];
    tagAll.click();
    chk('全部还原', $$('.cm-full-module').length, 172);
    chk('还原后恢复AI卡', $$('.cm-ai-card').length, 1);
  }

  // --- §16-8 hover 评论对象：滚动定位 + 临时高亮 ---
  var ref0 = $('.cm-reference[data-target-id="0"]');
  ref0.dispatchEvent(new Event('mouseenter'));
  chk('hover临时高亮', $$('.para.hover-preview').length, 1);
  chk('hover不改筛选状态', !$('#cmDrawer').classList.contains('parasec'), true);
  ref0.dispatchEvent(new Event('mouseleave'));
  chk('离开后高亮清除', $$('.para.hover-preview').length, 0);

  // --- §16-9 点击评论对象 → 单对象视图 ---
  $('.cm-reference[data-target-id="0"]').click();
  chk('点击进单对象视图', $('#cmDrawer').classList.contains('parasec'), true);
  chk('对象0计数', $('#cmCount').textContent, '105条');
  $$('.para').length && null;
  chk('对象0高亮', ($('.para.active')||{dataset:{}}).dataset.idx, '0');
  // 需求5: 点击评论对象气泡也要进单对象视图
  $('.cm-quote-back').click();
  var refBubble = $('.cm-ref-bubble[data-target-id="0"]');
  chk('评论对象气泡有 data-target-id', !!refBubble, true);
  chk('评论对象气泡 cursor pointer', getComputedStyle(refBubble).cursor, 'pointer');
  refBubble.click();
  chk('点击气泡进单对象视图', $('#cmDrawer').classList.contains('parasec'), true);
  chk('点击气泡高亮段0', ($('.para.active')||{dataset:{}}).dataset.idx, '0');
  $('.cm-quote-back').click();

  // --- §16-12 刷新后默认打开（reload 由外层统一处理） ---
  chk('右侧图标栏贴右(抽屉开)', Math.round(innerWidth - $('.rightrail').getBoundingClientRect().right), 0);
  $('#cmClose').click();
  chk('图标栏贴右(抽屉关)', Math.round(innerWidth - $('.rightrail').getBoundingClientRect().right), 0);
  chk('关闭后气泡隐藏', getComputedStyle($('.para-bubble')).display, 'none');
  chk('关闭后抽屉宽度0', Math.round($('#cmDrawer').getBoundingClientRect().width), 0);
  $('#rrComments').click();
  chk('重开评论模式', document.body.classList.contains('comment-mode'), true);
  chk('重开后恢复聚合视图', $$('.cm-full-module').length, 172);

  return out.join('\n');
})()
JSEOF
)

RESULT=$($BROWSER eval "$JS" 2>&1 | tail -n +1)

# agent-browser 可能把结果包在一层引号里，去掉首尾引号与转义
RESULT=$(printf '%s' "$RESULT" | sed -e 's/^"//' -e 's/"$//' -e 's/\\n/\n/g' -e 's/\\"/"/g')

# ---------- 输出结果 ----------
PASS=0; FAIL=0
echo "──────── 章节评论页冒烟测试（PRD §16）────────"
while IFS='|' read -r status name actual expected; do
  [ -z "${status:-}" ] && continue
  case "$status" in
    PASS) printf '  ✓ %-28s %s\n' "$name" "$actual"; PASS=$((PASS+1));;
    FAIL) printf '  ✗ %-28s 实际=%s 期望=%s\n' "$name" "$actual" "$expected"; FAIL=$((FAIL+1));;
  esac
done <<< "$RESULT"
echo "─────────────────────────────────────────────"
echo "  通过 $PASS 项，失败 $FAIL 项"
[ "$FAIL" -eq 0 ] || exit 1
