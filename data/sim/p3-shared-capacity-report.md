# P3 共享区段仿真验收

固定 10,000 人、30 个有向 OD、seed 20260922；结果全部为 simulated。
同一输入 SHA-256：`44bb2284e2df8bb3987631a1aac954e032284ca069a4bfcbbf543b9a0e3e58ab`。两次完整结果一致，共耗时 0.841 秒（本机计算耗时）。

| 场景 | baseline 延误（人·分钟） | guided 延误 | baseline 已服务 | guided 已服务 | guided 轮椅未满足 |
|---|---:|---:|---:|---:|---:|---:|
| 旧路线桶模型 | 15088.4 | 24682.4 | 10000 | 10000 | 0 |
| P3 共享区段模型 | 32103.4 | 32103.4 | 10000 | 10000 | 0 |
| P3 10% 残余容量压力输入 | 125121.6 | 123138.1 | 9690 | 9801 | 0 |

P3 引导改为逐人选择个人排序中最高的可行路线；空闲容量不会单独成为绕行理由。共享段逐一扣减，基线与引导使用相同物理容量及保护优先上车规则。
10% 场景仅用于运力敏感性与失败路径验证，不代表真实残余运力，也不承诺引导一定降低延误。未满足人数按物理上车容量计算，与未分配人数分开。

Explicit scenario resources pool directed shared segments once; each passenger consumes every segment on their route. Capacities remain simulated, stationary over the window; no verified residual loads, train-by-train boarding, inter-window carryover, or dedicated wheelchair berth capacity is modelled. Queue wait uses the largest route/segment bottleneck wait rather than summing overlapping estimates.

硬约束的 15 分钟上限只约束所选路线相对个人最优的额外行程；拥堵排队或未服务的等待不受此上限保证。轮椅可达性不等于已核实轮椅泊位吞吐量。

重新运行：`python scripts/precompute_sim_p3.py`；完整资源输入、前后结果、公平性及容量诊断见 `p3-shared-capacity-evidence.json`。
