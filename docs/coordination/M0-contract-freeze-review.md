# M0 契约冻结准备审计

## 基本信息

- 评审日期：2026-09-22
- 检查分支：`Mingquan-Xia`
- 检查基线：`204970366b44f9e8db970f0c80a5681e4a83476c`
- 评审范围：`03-contracts.md` §8、四个种子文件、现有 Schema、B 后端可运行性及 `origin/main` 集成状态
- 性质：这是冻结准备审计，不是 A / B / C 的全员签字结果。

## §8 检查表

| 检查项 | 状态 | 证据 | 负责人 | 下一步 | 阻止冻结 | 阻止 B 的 M0 关闭 | 阻止全团队 M0 |
|---|---|---|---|---|---|---|---|
| Schema 校验种子 | PARTIAL | Event / Signal Schema 与 Pydantic 一致，`event.seed.json` 双重校验通过；没有 Network / Route / Simulation Schema | B / C | C 为其负责的三类契约提供 Schema 与验证 | 是 | 是（T1.2 尚不能关闭） | 是 |
| 四个种子齐全且 A 可渲染 | PARTIAL | 四个文件存在且均为可读取 JSON；当前分支和 `origin/main` 都没有 `frontend/`，没有地图、三张事件卡及路线卡片的验收证据 | A（消费）/ B+C（提供） | A 提供实际渲染截图或验收记录，并确认不依赖 `ui_state` | 是 | 否（B 输入已提供） | 是 |
| `GET /api/health` 报告数据库与种子状态 | NOT STARTED | B 的 FastAPI 只有 `/api/signals`；仓库中没有 `/api/health` 路由 | C | C 按契约实现并补测试 | 是 | 否 | 是 |
| 假数据可跑的前后端进入 `main` | BLOCKED | `origin/main` 停在 `3de1ec2`，没有 `backend/` 或 `frontend/`；B 当前提交不在 `origin/main` 历史中 | 全员 | 分支成果经团队检查后按流程合并；A 仍需交付前端 | 是 | 是（尚未完成集成交付） | 是 |
| README 包含全部枚举与统一颜色 | PARTIAL | 颜色及通用枚举已列出；线路 ID 没有列全，且 `ERL` 与 `ERL_E` / `ERL_W` 冲突、`Signal.source_type` 尚无正式枚举 | B / 全员 | 先冻结线路与信号来源枚举，再同步 README、模型、Schema 与种子 | 是 | 是（T1.2 决策未完成） | 是 |
| B 的 Event / Signal 契约输入 | PASS | 3 个 Event、5 个 Signal、引用关系、严格字段和三档置信度均有自动化测试；Schema 可重复生成且无漂移 | B | 保持生成器与运行时模型同步 | 否 | 否 | 否 |

## 冻结前必须决定的契约问题

| 问题 | 当前事实与影响 | 建议 | 确认人 |
|---|---|---|---|
| 东铁线路 ID | 文档线路枚举用 `ERL_E` / `ERL_W`，Event、种子及 B 结构化代码使用 `ERL`，会影响 A 筛选和 C 图映射 | 选定唯一规范，并显式记录外部 `EAL` 到内部 ID 的映射层 | A / B / C |
| `Signal.source_type` | 模型仍是任意非空字符串，现有代码使用 `official`、`social`、`user` | 冻结为明确枚举后同步模型、Schema 和 README | A / B / C |
| 用户上报 provenance | API 使用 `real` 表示真实输入渠道，但内容仍未经核实 | 保留时必须在契约中写清“真实来源不等于事实已核实”；否则增加不改变字段含义的团队约定 | A / B |
| 复审与终止规则 | 骨架允许 `updated → published`，不允许 `published → rejected`，发布后编辑会进入 `updated` | 采用“编辑后重新批准、已发布事件用 expire 终止”的保守规则 | A / B / C |
| `updated` 期间生效语义 | 当前契约没有说明 A/C 使用旧发布版本、暂停事件还是立即使用修订版 | 建议在重新批准前继续使用最后一个已发布版本，但必须由 A/C 明确实现方式 | A / C（B 记录规则） |
| Event 删除 | EventStore 没有硬删除，审计表禁止更新或删除 | 正式禁止硬删除，以 `rejected` / `expired` 表示生命周期结束 | 全员 |
| C 负责的 Schema 和健康检查 | 三类 Schema 与 `/api/health` 均不存在 | C 给出交付时间，完成后由 B 复跑 §8 检查 | B / C |
| A 的 `ui_state` 与渲染 | `ui_state` 已从严格 Event 契约移除；当前仓库无 A 前端证据 | A 只从 `status`、`confidence`、`published_at` 等字段派生界面状态并提交验收证据 | A / B |

## B 的 M0 结论

- 已完成：Event / Signal 模型、SQLite 存储与追加式审计、B 的数据源和模拟流、用户 Signal 接口、结构化骨架、Event / Signal 种子及 Schema、最小审核状态机骨架。
- B 负责的 Event / Signal 技术实现已具备冻结候选条件。
- T1.2 目前不能正式关闭：线路与 `source_type` 枚举尚未冻结，C 的三类 Schema 缺失，A 的渲染证据和三方签字缺失。
- B 的 M0 代码部分已完成，但 B 的 M0 流程交付尚未完成，因为成果未进入 `main`，T1.2 也尚未获得团队确认。
- 全团队 M0 不能宣布完成；主要阻塞是 A 前端验收、C Schema 与健康检查、分支合并及全员契约决策。

## 团队签字区

- [ ] A：确认种子可以渲染地图、三张事件卡和路线卡片，并确认不依赖 `ui_state`
- [ ] B：确认 Event / Signal 契约、种子、Schema 与审核骨架
- [ ] C：确认 Network / Route / Simulation Schema，以及健康检查责任与交付
- [ ] 全员：确认线路 ID、`source_type`、审核转换、硬删除规则和正式冻结时间
