# P4 B：事实审阅与 A 可复制文案

核查日期：2026-10-11。基线为 `main` 的 `7d65823`。审阅了 `README.md`、`docs/submissions/data-and-ai-usage.md`、`docs/plan/07-demo-acceptance.md`、P4 对比/来源状态页面及现有验收报告。仓库中未找到最终 PPT 或视频文件，故本页不是最终媒体验收；A 仍负责最终文案和画面。

## 需 A/C 依据同版本证据修订

| 位置 | 当前风险 | 建议 |
|---|---|---|
| `docs/plan/07-demo-acceptance.md` §1 2:00–3:10 | 写死两画像首选不同、31–38/42–50 分钟和“全港 4 辆低地台小巴”。当前对比页可诚实显示首选相同；固定数字和车辆数不能作为已验事实。 | C 提交同事件、OD、时间和图快照的两份路线响应后再填数；若相同或无路线，照实展示。 |
| 同文件 §1 3:10–4:20 与 §2 | “6,140 人/小时”、P95 37→14 分钟、过载清零和固定比例来自旧示意，不能套用新场景。 | 使用当前同版本仿真文件的原始数字及 `simulated` 标签；负改善也必须如实展示。 |
| 同文件 §1 1:40–2:00 | “发布后 2 秒内”没有对应线上同版本页面计时。 | 改为“批准后刷新图快照并重算”，显示现场实际 `elapsed_ms`，不承诺生产环境时延。 |
| 同文件 §1 早发现 | 社媒三条和置信度阶梯是演示夹具，不是已接通受限社媒的实况。 | 标“模拟信号演示”；真实公告读取成功也不等于产生合格 Signal 或人工批准。 |
| `README.md`、Data/AI statement | README 已列来源/重规划状态；Data/AI statement 的核查日期仍是 9 月 30 日。 | A 最终同步核查日期、部署版本和是否已接五画像目录；不得把本地测试/模拟结果说成线上实测。 |

现有 P4 页面已显示来源状态，并在两画像首选相同时明确说“不制造差异”；这比旧脚本诚实。它不替代固定场景的路线差异、无障碍资料和线上发布计时验收。

可直接复制的中文口播：

> 这是一个大围至金钟走廊的学术原型。模拟事件须人工审核后才会进入路线图；画像和天气影响系数是设计假设，路线与票价由确定性服务计算。对比页如实展示不同画像的路线，包括首选相同或没有可行路线的情况；线上效果仍待实测。

可直接复制的英文 PPT 文案：

> This is an academic prototype on a modelled Tai Wai–Admiralty corridor. Only human-approved events affect routing. Persona defaults, weather effects and passenger demand are simulated assumptions; route and fare figures come from deterministic tools, not the language model. The comparison reports what the engine returns, including identical or infeasible first choices. Production performance remains unverified.

无障碍文案：

> 轮椅画像强制排除阶梯、小巴及非低地台巴士，并限制步行最多 400 米；这些是算法硬约束，不代表底层设施资料已逐站认证。无可行路线时须明确显示，不推荐违反约束的替代路线。

来源文案：

> HKO 公开警告可作为天气事件来源，但步行惩罚、可靠性和停运阈值为模拟估计。港铁公开公告请求成功不等于有合格事件；是否发布仍由人决定。

旧 B 分支的浏览器互测记录见 `codex/b-p3-p4-closeout` 的 `runs/round-009/evidence/browser/`：无 AI 查询、轮椅、受控雨天/无路线页面、来源失败、事件发布/撤回和断网恢复。该证据对应旧分支与本机环境，**不能冒充当前 `main` 或线上复验**；最终 PPT/视频仍需 A 逐页核对、C 确认路线与仿真数字。
