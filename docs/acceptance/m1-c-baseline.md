# M1 C 侧集成验收基线（待后续路线／数据交付最终核验）

**C 收到 published event 之后的本地组合应用验收通过；完整 M1 发布与前端刷新链路未验收。** 统一命令 exit **2** 表示已执行 C 检查通过、外部依赖仍未交付；不是完整端到端通过。

## 基线与变更范围

2026-09-24 fetch 确认 `upstream/ZYC-M1` 为 `75fe0b05bb54ff78cac44f39e485a968760a8920`。新建独立 worktree `m1-c-acceptance` 与分支 `codex/m1-c-acceptance`，未复用旧 `agent/c-integrator` / e825794 工作区。PR base 必须为 **ZYC-M1**，没有修改或更新 main。

新增文件：

- `tests/cross_module/test_m1_receipt.py`：4 项新增验收，运行实际组合应用工厂；每次使用独立临时 SQLite，测试结束恢复 runtime。
- `scripts/integration/m1_acceptance.py`：可复现编排、HTTP 接口清单、源码 SHA256、原始性能样本与汇总。
- 本报告及 `docs/acceptance/evidence/m1-baseline/`：真实测试日志、首次缺依赖错误和最终结果。

仅修改 Integrator 的三个授权目录；不改 graph/engine、data、B 事件服务或 A 前端。源基线加本 PR 的验收文件一起受测，各文件 SHA256 见 summary；执行前后指纹相同。

## 避免重复的覆盖边界

原 `test_module_chain.py` 已验证 JSON adapter→RouteCandidate、Route→Sim 参数/缓存、内存事件触发路线/仿真重算和实际 AI handlers。原 Route `test_m0_timing.py` 已验证时间表、闭边/降容与快照不可变。因此本轮不重写这些测试，而将缺少的 **当前组合应用 HTTP 缓存与快照一致性** 补上：

| 新增检查 | 实测 |
|---|---|
| 缓存过的 HTTP 路线→C 接收 published event→公开 snapshot/meta→新路线 | 通过；先证明旧候选确实经过目标边，闭边后两方向 affected_edges 可见；空 event_ids 不能绕过闭边 |
| expired 恢复与旧版本 published 重放 | 通过；路线恢复，旧版本不覆盖新 snapshot |
| pending_review/rejected 接收边界 | 通过；不关闭路线；没有要求所有非生效事件都必须保留同一 snapshot ID |
| 非法 capacity_factor 的新事件 | 通过；拒绝后 snapshot 和 HTTP 路线结果保持原样 |
| LLM 禁用下公开 chat 查询 | 通过；真实 C handlers 返回与闭边后 HTTP 相同的路线，LLM transport 调用为 0 |

未增加假的 B 发布 API；事件只通过实际 `SnapshotStore.update_event` 注入，代表 **C 收到消息**。HTTP 使用 FastAPI TestClient/ASGI，不冒充网络部署测试。默认应用的 B SignalStore 使用临时数据库，未写生产数据库文件。

## 命令与结果

先安装仓库声明的后端依赖与 pytest（本轮运行时最初缺 jsonschema，补装 4.26.0 后重跑，原错误保留在 `owner_regression.initial_missing_dependency.txt`）。Python、平台与实际包版本见 [summary.json](evidence/m1-baseline/summary.json)。

```text
python -m pip install -r backend/requirements.txt pytest
python -m scripts.integration.m1_acceptance --output-dir docs/acceptance/evidence/m1-baseline --samples 25
```

编排设置 `PYTHONPATH=<repo>;<repo>/backend`（Windows）、`AI_ENABLED=false`、`LLM_ENABLED=false`、`OFFLINE_MODE=true`，编译缓存放临时目录。独立执行子命令时使用同样环境。

| 子命令 | 结果 |
|---|---|
| python -m compileall -q backend/app | exit 0 |
| python -m unittest discover -s tests/cross_module -v | exit 0，20 项通过（含新增 4 项） |
| python -m unittest discover -s tests/integration -v | exit 0，40 项通过 |
| python -m pytest -q -p no:cacheprovider --import-mode=importlib backend/app/engine/tests backend/tests | exit 0，222 项通过；2 项既有依赖弃用警告 |
| python scripts/validate_data.py | exit 0 |
| python scripts/preflight.py | exit 0 |
| 组合应用 HTTP 接收边界探针 | 7 个断言全部通过，候选 10→9；snapshot ID 改变；LLM 调用 0 |
| 两组性能测量 | 每组 25 次，所有快照切换 <2s；完整原始样本保留 |

测试集合存在交叉，不简单累加。统一命令只在可执行检查失败时 exit 1；exit 2 始终保留本轮未验收的 B/A 与后续交付边界，没有 skip/xfail 掩盖代码失败。

## 性能证据

单位 ms，P95 使用 nearest-rank；在同一进程串行运行，每次新建 engine。cold 包含 JSON 读取、构图和首次查询，不包括 Python 进程启动，操作系统文件缓存可能已热。cached 使用相同键并确认 cache hit；receipt 从调用 update_event 到重算返回，不含 B/A、HTTP 或联网。

| 输入 | 新 engine + query P95 | cached query P95 | snapshot swap P95 | C receipt→route P95 |
|---|---:|---:|---:|---:|
| synthetic | 6.607 | 1.904 | 0.560 | 4.607 |
| repository_seed | 16.077 | 2.413 | 0.962 | 16.350 |

仓库 seed 样本的路线数量为 10→10，但候选 ID 集合确实改变且闭边被排除；“数量相同”不等于没有重算。性能仅是该机器、该输入的本地证据，不是生产负载 SLA，也不提前宣布 M3/M4 性能验收完成。

## fixture 与真实性

复用 `tests/cross_module/fixtures/scenario.json`、engine `network.synthetic.json` / `events.synthetic.json`、消费者 `simulated-contracts.json`。新增事件从实际已选候选的一条边生成，`provenance=simulated`，confidence note 明示测试来源，没有编写真实交通线路、容量或班距。

第二组性能读取当前 network/routes seed 的 OD，经已有 SeedDataAdapter 转为 simulated 模型；正式线路数据真实性、ZCode 后续数据更新及路线 PR 的最终行为不在本次基线证明范围。所有计时、候选与注入事件均为 simulated 输入的结果。

## 接口依赖与最终核验条件

| 责任/依赖 | 现状与下一步 |
|---|---|
| B 发布 API | 当前组合应用 OpenAPI 没有 GET /api/events/published、POST /api/events/{id}/review、GET /api/stream/events；具体清单保存在 summary。B 有事件模型/存储/审核服务，不能因此认定 HTTP 发布管道已接通。 |
| B→C 投递 | 需明确 published/updated/expired 消息投递、版本、失败/重放语义；本轮仅直接调用 C 接收边界，没有证明 B 已自动驱动 snapshot。 |
| A 动态刷新 | `frontend/src/App.tsx` 当前使用 seedDataSource 和固定 snapshot；真实发布→地图变色/路线卡刷新尚无验收证据。未修改前端或假装 UI 已通过。 |
| Codex 路线 PR | 收到对应 PR/SHA 后，在 ZYC-M1 合入后的基线上重跑本命令，核对闭边、版本/缓存、公开 RouteCandidate 与性能变化。当前不是该 PR 的最终验收。 |
| ZCode 数据结果 | 收到精确数据提交、来源/转换记录及适配说明后，核对数据可加载与 provenance，再重跑相关查询与性能；不能拿模拟结果替代数据验证。 |

PR 交付的是可独立运行的验收基线。后续更新仍只修改授权的验收目录，保持 PR base 为 ZYC-M1。main、B 服务与 A 前端均不在本轮写入范围。
