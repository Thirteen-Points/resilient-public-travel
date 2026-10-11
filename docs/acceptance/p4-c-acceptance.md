# P4-C 本地验收记录

日期：2026-10-06（Asia/Shanghai）。工作范围：本地仓库与 **ZYC-P4**。
状态：C 的仿真、部署准备、技术离线包、性能门禁和 CI 配置已实现并本地验证；
生产验收与仓库管理员设置尚未执行，不能据此宣布 P4 线上验收通过。

## 工作区与版本

- 起点为 `d952216cd6360c73fc01b17e6e8b4de30865f045`，检查时最新 main
  与远端 ZYC-P4 指向同一提交；没有向 main 写入、部署或修改仓库设置。
- 切换前 ZYC-M1 的既有已跟踪/未跟踪内容保存在 stash
  `16bfda8050bb4db5bcd94f6607133a978f740be2`，未应用到 ZYC-P4。
  `.codex/`、`.verification/` 与后来出现的 `docs/research/` 不属于本次提交。
- 本地演示前后端 build identity 都记录上述完整 SHA；测试时工作区包含本次修改，
  因此该 SHA 是 **base SHA**，不是干净生产构建证明。预计算结果记录
  `source_dirty: true` 和 generator hash，离线 ZIP manifest 记录文件哈希及 dirty 状态。
  最终本地提交 SHA 由 Git 提交记录与交付消息提供。
- Python 3.12.14、Windows 11、Node 24.19.0、无头 Edge；复用本地已装依赖。
  标准库测试临时目录和浏览器隔离数据库已固定到项目 `.cache/`。

## 修改摘要

1. `precompute_sim_p3.py` 保留冻结输入、评分策略和共享容量模型，增加场景/输入/模型
   版本、真实生成时间、query time、单位、SHA、dirty 标识；正常和压力场景各重复验证。
   修复历史 CRLF 哈希与 LF 检出之间的可移植性，仍拒绝文本内容变化。
2. `preflight.py` 默认只检查本地文件，兼容启动前调用；可选检查 health/deep/meta、
   精确的两个缓存响应、build SHA、离线模式、前端文件哈希和备用媒体。
   不就绪、文件缺失、身份/缓存不一致、严格媒体门禁失败均返回非零状态。
3. 增加无安装步骤的本地前后端启动器、Windows/Linux 入口、允许清单 ZIP 打包器，
   不打包 `.env*`、SQLite、日志或依赖目录。Windows 清理完整的本次后端进程树。
4. 增加固定场景/路线性能门禁、离线浏览器与媒体解码验证；补齐 P3 浏览器的陈旧
   merge 成功提示断言，同时断言真实 API `state=merged`，未改产品提示文案。
5. P3 regression 保留原检查名，新增 ZYC-P4 push、固定输入/性能、自检、P3 浏览器、
   离线前端构建/打包/浏览器与媒体核验；`always()` 保存失败证据。
   Administrator bundle 也增加 ZYC-P4 push。部署步骤和线上空白记录表已补齐。

路线评分代码、policy fixture、偏好预设、前端产品文案、网络 seed 与冻结 route input
在本次 diff 中均无变化。接口只给两份 P3 缓存结果增加元信息；旧 M0/M2 调用保持可用。
完整示例与单位解释见 [响应契约](../../contracts/sim-precomputed.md)。

## 仿真复现结果

输入：10,000 人，30 个有向 OD，seed `20260922`，60 分钟窗口，44 个共享有向区段。
`input_version=m2-six-station-v1`；`model_version=shared-directed-segments-v1`。
冻结出发时间 `2026-09-22T08:20:00+08:00`；生成时间
`2026-10-05T16:23:10+00:00`。

历史输入字节哈希（CRLF）：
`2dd88817730f7f7c620123a81de9e434b63ac09530d0517f63e3ff7e06ca5bec`。
P4 统一 LF 的输入哈希：
`f50d68f5eaa7cba0cfaabce6e19a3c50de080becd457d8e8533be6e7789247f1`。
这是同一文本的换行差异，不是输入再生成。网络与 policy 历史哈希同样按此兼容校验。

| 场景 / 策略 | 延误（人·分钟） | P95 等待（分钟） | 已服务（人/窗口） | 未服务（人/窗口） | 超载路线桶 / 共享区段 |
|---|---:|---:|---:|---:|---:|
| 正常 baseline | 32,103.4 | 3.4 | 10,000 | 0 | 0 / 0 |
| 正常 guided | 32,103.4 | 3.4 | 10,000 | 0 | 0 / 0 |
| 10% 运力 baseline | 125,121.6 | 12 | 9,690 | 310 | 0 / 6 |
| 10% 运力 guided | 123,138.1 | 12 | 9,801 | 199 | 0 / 0 |

正常场景延误收益 **0%**；压力场景延误减少 **1.6%**，增加服务 111 人，仍有 199 人缺口。
guided 压力场景 `unassigned_demand=unstoppable_demand=199`；baseline 的未服务 310 人
是分配后不能上车，不能用 baseline 的 `unassigned_demand=0` 隐去该缺口。
两策略各自的 44 个 resource ID 唯一；已有共享区段测试确认重叠路线使用同一预算。
每个场景连续 3 次完整 core 输出一致且等于落盘结果。变化的生成时间不参与核心结果相等性。
旧 M0 场景仍显示 **-8.8%**，浏览器直接核对 API 原值，没有调权改结果。

边界：所有结果为 `simulated`。10% 因子是人为压力敏感性输入；没有观测外部乘客、实时
剩余运力或已验证轮椅专用泊位吞吐量。队列是瓶颈近似，不含逐班座位传播、跨窗口滞留。
15 分钟额外行程约束不等于排队等待保证。缺失份额/测量信息继续显示缺失。

## 本地性能与运行证据

计时 `2026-10-05T16:30:18+00:00`，nearest-rank P95，未测生产/WAN延迟：

| 检查 | 样本 / 结果 | 门禁 |
|---|---|---|
| 正常 1 万人执行 | 0.3858 / 0.4165 / 0.4004 秒 | 每次 <= 30 秒，通过 |
| 压力 1 万人执行 | 0.3865 / 0.4957 / 0.5952 秒 | 每次 <= 30 秒，通过 |
| 新引擎创建 + 路线查询 | 60 次，P95 21.929 ms | 包括初始化，非缓存命中 |
| 缓存路线查询 | 60 次，P95 2.056 ms | 单独列出，不代替查询门禁 |
| 本地 HTTP 顺序查询 | 60 次，P95 61.521 ms，最大 74.322 ms | <= 1,500 ms，通过 |
| 本地 HTTP 4 并发 | 30 次，P95 107.189 ms，最大 107.261 ms | <= 1,500 ms，通过 |

原始耗时和指标保存在 [性能 JSON](evidence/p4/c/local-performance.json)。两种执行计时包含
run_m2_multi_od 计算，不是读取预计算 JSON 的耗时。HTTP 使用只读路线查询和不同出发秒值。

- 完整后端：**543 passed，264 subtests passed**（30.67 s）；一个现有 TestClient
  依赖弃用提示。独立 P4 预检异常测试 54 项通过；模拟缺数据、重复共享资源、篡改前端、
  错误 API/身份/缓存、缺媒体均能报告失败，负收益原值不被改写。
- 前端：**88 passed / 10 files**；TypeScript 与生产 build 通过，保留现有大 chunk 提示。
  管理员 build 与已提交静态包一致。
- M2 浏览器通过：三次刷新 188 / 230 / 123 ms，轮询撤回 3,371 ms；均为隔离本地。
- P3 浏览器通过：三轮真实 confirm click 后地图/路线渲染与撤回、断网恢复、手机端检查。
  三轮地图 1,868 / 2,893 / 2,384 ms；路线 1,697 / 2,410 / 2,206 ms；撤回 2,823 ms。
  首次因陈旧提示文本断言失败的记录被保留，修复后重跑通过，不能计作生产证据。
- `git diff --check`、种子契约校验、data layer 结构校验通过。数据来源真实性仍遵从
  provenance ledger 的既有人工核验限制。

## 离线包与备用媒体

[启动/五分钟演示/故障切换说明](../../deploy/offline/README.md)。技术包路径
`.cache/offline/resilientroute-offline.zip`（本地生成，未把构建缓存放进 Git）。
ZIP 全部 manifest 哈希与文件一致；没有 `.env*` 或 SQLite。
包在项目内 `.cache/p4-extracted/` 解压后，使用已准备 Python 无下载启动成功。

离线浏览器明确阻断 `fonts.googleapis.com` 与 `tile.openstreetmap.org`；本地 health、
查询、三个预计算场景和 assumptions 均正常，无 page error。它证明无需外部网络服务，
不代表在现场机器上已经实际拔网线演练。

- `deploy/offline/media/demo.webm`：真实 UI 的静音 **300 秒**录屏；裁掉录制器末尾
  多余静态停留帧，未注入模拟返回值或重写画面。Edge 解码、seek、五个片段截图通过。
- `deploy/offline/media/slides.pdf`：6 页 C 技术备用 PDF，基于实际截图/运行指标制作；
  已渲染逐页检查无裁切或重叠。用本地 Edge/Chromium 与 PDF 阅读器故障切换。
- 媒体格式头自检是必要条件；解码/渲染证据另列。A 与 reviewer 尚需签收，或用团队
  终版 PPT 导出的 PDF 替换技术备用稿；不是声称团队终版演示已经批准。

媒体/本地运行摘要见 [证据索引](evidence/p4/c/local-summary.json)。

## CI、线上与未完成项

本次只在本地 ZYC-P4 提交，未推送或触发远端 Actions；**此次 CI 状态未验证**。
本地绿灯不能填成 CI 绿灯。工作流失败仍为失败状态，`always()` 上传 JUnit、浏览器日志、
截图、性能与离线包证据，保留 14 天。实际检查名称由仓库管理员在对应 PR SHA 再确认：

| Required check | Workflow | 管理员动作 |
|---|---|---|
| `Backend, frontend and browser` | P3 regression | 确认实际 run 后设为 required |
| `Container recreation persistence` | P3 regression | 确认容器重建证据后设为 required |
| `verify` | Administrator bundle | 确认检查名，再配置保护/审阅/绕过策略 |

| 未完成项 | 状态 / 负责人 / 下一步 |
|---|---|
| 此分支实际 Actions 与 Docker 重建 | 未验证；分支维护者 / C，后续获准推送 ZYC-P4 后检查运行与证据 |
| 生产 deployment SHA、健康与性能 | 未验证；部署管理员 + C，按 runbook 指定 release/origin 与计时 |
| 线上发布、撤回、自然过期、断网恢复 | 未验证；B reviewer + A + C，在有权限的部署执行三轮并保留失败 |
| 重部署后 Signal/Event/audit、管理员设置/usage | 未验证；部署管理员 + B + C，备份三个库，保留原 volume/disk/key 后比对 |
| Required checks / 仓库保护 | 未验证；仓库管理员确认实际名称并设置 |
| 现场完全断网、目标机依赖/媒体故障切换 | 待签收；C + demo owner，按说明在目标机器演练 |
| 团队最终 PPT 与演示签收 | 待 A / reviewer，批准或替换 C 技术备用 PDF |
| 权重结论后的全员回归 | 等结论；A / B / C，记录新输入/版本后跑相关回归 |

权限目前没有执行验证，不能推定拥有 reviewer、部署或仓库管理员授权；这些步骤保持
未验证。完整操作见 [部署验收 runbook](../../deploy/P4-ACCEPTANCE.md)，使用
[线上记录模板](evidence/p4/c/online-template.json) 单独记录环境、部署 SHA、时间、操作人、
Signal/Event/audit 与媒体证据；未知计时保留 null，不用本地数据补生产记录。

## 2026-10-11 merge reconciliation

Merged main through `d07730d84df9f9db11b0a439680e4b503997781d`, including the
first/last boarding-window corrections. Historical network input is now stored
at `data/sim/frozen-network.seed.json`; its original content hash is preserved.
Only the manifest network path changes. P3 caches and capacity evidence are
regenerated with current generation metadata and the new manifest hash, and
all simulation core fields are checked against the previous recorded results.
The earlier dated evidence and media above retain their original build/input
identity; they are historical local checks, not evidence of this merged build.
CI uses the current P4 browser suite, plus offline production and media checks.
