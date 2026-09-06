#!/usr/bin/env bash
# publish.sh —— 一键发布到 GitHub Pages
#
# 用法：
#   ./publish.sh                # 自动 commit（缺省消息）+ push + 验证线上
#   ./publish.sh "fix: xxx"     # 指定 commit 消息
#
# 流程：
#   1. git add -A（.workbuddy/ 等由 .gitignore 排除）
#   2. 若有改动 → commit（pre-commit 钩子自动跑 262 项冒烟测试，失败即中止，不会发布）
#   3. push origin master
#   4. 轮询 GitHub Pages 构建状态至 built（通常 1-2 分钟）
#   5. curl 验证线上 200 且评论数据块已部署
#
# 线上：https://moomin121.github.io/chapter-comments/
# 仓库：https://github.com/moomin121/chapter-comments
set -euo pipefail

REPO="moomin121/chapter-comments"
URL="https://moomin121.github.io/chapter-comments/"
BRANCH="master"

cd "$(git rev-parse --show-toplevel)"

echo "── 1/4 检查改动 ──"
git add -A
if git diff --cached --quiet; then
  echo "工作区无改动。"
else
  MSG="${1:-deploy: 发布更新 $(date +%F)}"
  echo "── 2/4 提交（pre-commit 钩子自动跑冒烟测试）──"
  git -c commit.gpgsign=false commit -m "$MSG"
fi

# 本地是否领先远程（有未推送的 commit）
UNPUSHED=$(git rev-list --count origin/${BRANCH}..HEAD 2>/dev/null || echo 1)
if [ "${UNPUSHED}" -eq 0 ]; then
  echo "── 本地与远程一致，无需推送 ──"
else
  echo "── 3/4 推送 origin ${BRANCH} ──"
  git -c commit.gpgsign=false push origin "${BRANCH}"
fi

echo "── 4/4 等待 Pages 构建并验证 ──"
# 等待最新一次构建：commit 对应当前 HEAD 且状态为 built
HEAD_SHA=$(git rev-parse HEAD)

echo -n "  构建: "
for i in $(seq 1 30); do
  LATEST=$(gh api "repos/${REPO}/pages/builds/latest" 2>/dev/null) || LATEST='{}'
  BUILD_SHA=$(echo "${LATEST}" | jq -r '.commit // ""')
  STATUS=$(echo "${LATEST}" | jq -r '.status // ""')
  if [ "${BUILD_SHA}" = "${HEAD_SHA}" ] && [ "${STATUS}" = "built" ]; then
    echo "built ✓"
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "超时（最后状态: ${STATUS:-未知}, commit: ${BUILD_SHA:-未知}）。可稍后手动访问 ${URL} 确认。"
    exit 1
  fi
  echo -n "."
  sleep 10
done

HTTP=$(curl -s -o /dev/null -w '%{http_code}' "${URL}")
echo "  线上 HTTP ${HTTP}"
[ "${HTTP}" = "200" ] || { echo "✗ 线上不可达"; exit 1; }

if curl -sL --compressed --max-time 120 "${URL}" | grep -q "GENERATED_COMMENT_DATA_START"; then
  echo "  评论数据块已部署 ✓"
else
  echo "✗ 页面可达但未检测到评论数据块标记"
  exit 1
fi

echo ""
echo "✅ 发布完成：${URL}"
