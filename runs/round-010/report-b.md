# B P4 问答与事实审阅报告

日期：2026-10-11。**状态：partial**（B 的 P4 文案交付已完成；A 的最终 PPT/视频与 C 的同版本路线/仿真数字仍待确认）。

## 工作完成与文件变更

- `docs/plan/07-demo-acceptance.md` §4：16 条问答逐条改写，避免旧的“6,140 人/小时”“全港 4 辆低地台小巴”、模型单价和线上性能承诺；按 `main` 当前 P4 页面，说明对比会如实显示首选相同、来源状态已有本地展示。
- `docs/coordination/P4-B-material-review.md`：对旧演示脚本、README、Data/AI statement 及当前页面做事实核查，交付中英文可复制文案；没有修改 A 所有的镜头脚本和最终媒体。
- `runs/round-010/task-b.md`、本报告：记录范围、检查与交接。未移植 P3 代码、旧在线采集或旧 B 分支浏览器证据到本 PR。

## 发现与证据

- 当前 `main` 的 `frontend/src/components/ComparePage.tsx` 明确在两画像 top1 相同时不制造差异；`frontend/src/components/SourceStatus.tsx` 已展示来源状态。故旧 B 文案关于“来源状态页面尚未做”的判断已改，仍不宣称生产环境已验收。
- `docs/plan/07-demo-acceptance.md` §1/§2 仍含旧固定路线、分钟数、低地台小巴和仿真收益数字；它们属于 A 最终脚本所有权，本轮只在事实审阅中列修改建议。
- `docs/coordination/T2.6-real-model-acceptance.md` 仍标 partial，真实模型费用不能据旧示意报价。
- 旧 B 分支 `codex/b-p3-p4-closeout` 的 `runs/round-009/evidence/browser/` 有本地角色互测截图/录屏，但它不是本轮 `main` 的浏览器复测或线上证据。最终 PPT/视频文件在当前仓库未找到，因此未审阅最终成品。

## 实际检查

- PowerShell 读取 §4 并统计 `**Qn.` 与 `> ` 答案行：**16 问、16 答、超过三句的答案 0**。
- `rg` 核对旧数字：`6,140`、`4 辆低地台` 等只剩在未改动的 §1/§2 脚本；§4 已删除对应断言。
- `git diff --check`：通过，只有 Windows LF/CRLF 转换提示。文档变更不需代码单元测试；已人工核对新文案和本轮允许文件清单。

## 问题、风险与下一步

- A 应逐镜头替换 §1/§2 的旧数字，并对最终 PPT/视频和 Data/AI statement 的版本日期签字；B 的建议不能冒充 A 已完成。
- C 应给同一事件/OD/时间/图快照的两画像路线及仿真输出；若首选相同、无路线或负改善，最终演示要照实说明。
- T2.6 真模型、真实来源合格 Signal、线上人工发布和线上计时仍须另行验收。P4 整体不能因为本问答 PR 而标完成。
