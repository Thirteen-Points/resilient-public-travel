# P4 B 事实审阅与 A 可复制文案

日期：2026-10-05。审阅了根目录 `README.md`、`docs/submissions/data-and-ai-usage.md`、`docs/plan/07-demo-acceptance.md`；仓库中未找到可核实的最终 PPT 或视频文件，所以**未**宣称已审完最终媒体。B 未改 A 的演示脚本或页面。

## 必须由 A/C 对照证据修订的地方

| 位置 | 当前风险 | 建议 |
|---|---|---|
| `docs/plan/07-demo-acceptance.md` §1 2:00–3:10 | 固定宣称两画像 top1 不同、31–38/42–50 分钟、全港 4 辆低地台小巴；当前同 OD top1 相同，且小巴数字未被现有证据支持。 | 删除预设路线/分钟/车辆数；由 C 在固定 OD 和获批事件下给出两份真实响应后再填入。 |
| 同文件 §1 3:10–4:20 与 §2 | “6,140 人/小时”、P95 37→14 分钟、过载清零、固定比例是旧场景数字；不能套用当前仿真。 | 使用当前同版本仿真文件的实际数字与 `simulated` 标签；若压力场景为负改善，照实展示。 |
| 同文件 §1 1:40–2:00 | “发布后 2 秒内”缺该页面/线上同版本计时。 | 改为“批准后刷新图快照并重算；现场显示实际 elapsed_ms”。 |
| 同文件 §1 早发现 | 社媒三条及置信度 0.20→0.55→0.90 是演示夹具，不是已接通社媒实况。 | 标“模拟信号演示”；MTR 公开公告真实读取尚未形成合格 Signal。 |
| `README.md` 与 Data/AI statement | 总体边界大体准确；README 的 API 表尚未列画像目录和来源状态，Data/AI statement 的核查日期为 9 月 30 日。 | A 合并后同步接口表、核查日期和当前 partial 范围，勿把 local/模拟改写为 live/实测。 |

可直接复制的中文口播：

> 这是一个大围至金钟走廊的学术原型。模拟事件须人工审核后才会进入路线图；画像和天气影响系数是设计假设，路线与票价由确定性服务计算。当前来源采集、画像差异和线上性能各有未完成验收，我们会在画面上分别标明。

可直接复制的英文 PPT 文案：

> This is an academic prototype on a modelled Tai Wai–Admiralty corridor. Only human-approved events affect routing. Persona defaults, weather effects and passenger demand are simulated assumptions; route and fare figures come from deterministic tools, not the language model. Live ingestion, distinct persona outcomes and production latency remain partially validated.

无障碍文案：

> 轮椅画像强制排除阶梯、小巴及非低地台巴士，并限制步行最多 400 米；这些是算法硬约束，不代表底层设施资料已逐站认证。无可行路线时须明确显示，不推荐违反约束的替代路线。

来源文案：

> HKO 公开警告可作为天气事件来源，但步行惩罚、可靠性和停运阈值为模拟估计。港铁公开公告请求成功不等于有合格事件；是否发布仍由人决定。

建议 A 在 PPT/视频最终导出前，按 `docs/plan/07-demo-acceptance.md` 的问答库和上述替换文本逐页复核，再由 C 对路线/仿真数字和证据版本签字确认。
