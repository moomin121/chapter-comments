#!/usr/bin/env bash
# 章节评论页冒烟测试
#
# 用法： ./test/smoke-test.sh
# 依赖： agent-browser（/opt/homebrew/bin/agent-browser）、python3
#
# 覆盖：
#   1. 数据完整性 — 190 段 / 145 气泡 / 章评 621 / 段评 5744
#   2. 布局铁律   — 右侧图标栏贴 viewport 最右（抽屉开、关两种状态 gap 都必须为 0）
#   3. 交互       — 点击气泡高亮对应段、抽屉切段评视图、段评 tab 列出 190 项
#   4. 零值段     — count 为 0 的段不渲染气泡
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
  echo "✗ 服务器未起来（$URL）"; exit 1
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
  chk('章评数(标题气泡)', $('#chapBubble').textContent, 621);
  chk('章评数(抽屉标题)', $('#cmCount').textContent, 621);
  chk('段评总数', $('#chapSecTotal').textContent, 5744);
  chk('章节标题', $('#chapTitle').textContent, '第1章 面试');
  chk('作品名', $('#chapWork').textContent, '没钱修什么仙？');
  chk('作者', $('#chapAuthor').textContent, '熊狼狗');

  // --- 1b. 左侧目录（Figma 稿）---
  chk('左栏分组数', $$('.lp-group').length, 2);
  chk('左栏章节项数', $$('.lp-item').length, 16);
  chk('左栏第一分组', $('.lp-group:nth-of-type(1) .nm').textContent, '作品相关');
  chk('左栏第二分组', $('.lp-group:nth-of-type(2) .nm').textContent, '正文卷');
  chk('左栏激活章节', $('.lp-item.active .nm').textContent, '第1章 面试');
  chk('左栏激活字数', $('.lp-item.active .wc').textContent, '3359');
  chk('左栏已完成章(1-6)', $$('.lp-item.done').length, 6);
  chk('左栏带图章节(第8章)', $$('.lp-item .pic').length, 1);
  chk('左栏无残留作品选择器', !!document.querySelector('.lp-book'), false);

  // --- 2. 布局铁律：抽屉展开时图标栏贴右 ---
  var rail = $('.rightrail').getBoundingClientRect();
  chk('图标栏贴右(抽屉开)', Math.round(innerWidth - rail.right), 0);

  // --- 3. 零值段不渲染气泡（第 5 段 / idx=4 是零值段）---
  chk('零值段无气泡(idx4)', !!$('.para[data-idx="4"] .para-bubble'), false);
  chk('非零值段有气泡(idx17)', !!$('.para[data-idx="17"] .para-bubble'), true);

  // --- 4. 交互：点击高热度气泡 ---
  $('.para-bubble[data-idx="17"]').click();
  var act = $('.para.active');
  chk('点击气泡后高亮段', act ? act.dataset.idx : 'none', 17);
  chk('抽屉切段评视图', $('#cmDrawer').classList.contains('parasec'), true);
  chk('段评视图标题', ($('.cm-list').textContent||'').indexOf('第18段') >= 0, true);

  // --- 5. 段评 tab ---
  $('#cmBack').click();
  $('#cmTabPara').click();
  chk('段评tab列出全部段', $$('#cmList [data-goto]').length, 190);

  // --- 6. 布局铁律：抽屉折叠后图标栏依然贴右 ---
  $('#cmClose').click();
  var rail2 = $('.rightrail').getBoundingClientRect();
  chk('图标栏贴右(抽屉关)', Math.round(innerWidth - rail2.right), 0);

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
