# M2 六站多 OD 仿真对比

- provenance：`simulated`；seed：`20260922`；OD：`30`；候选路线：`231`（去重 ID `231`）
- 无路线 OD：`0`；查询错误：`0`；跨 OD 重复 route_id：`0`
- 结果为模拟算法输出；不能解释为实测客流、真实运力或运营预测。
- 共享线路段：7 条线路对应多个 route_id；当前路线级容量不能按共享线路拆分。

| 指标 | baseline | guided |
|---|---:|---:|
| 延误总量（人·分钟） | 15088.4 | 24682.4 |
| 平均延误（分钟/人） | 1.5 | 2.5 |
| 物理运力已服务人数 | 10000 | 10000 |
| 未满足需求（物理运力口径） | 0 | 0 |
| 未分配需求 | 0 | 0 |
| 超目标容量路线数 | 0 | 0 |
| 轮椅乘客服务率 | 1.0 | 1.0 |
| 无障碍候选集缺失 OD 数 | 0 | 0 |

## 本次结果解读

本场景 guided 总延误比 baseline 高 63.6%；两组均未出现目标容量超载或未满足需求，因此本次结果没有显示引导策略带来延误收益。

## 数据与运力限制

C-Route exposes route-level bottleneck capacity, not segment-level shared-service identities; distinct route_ids with overlapping legs cannot be safely pooled from current fields alone.

不同路线可能共享部分线路或区段；当前接口没有按区段暴露可分配运力。结果中的 route_id 容量桶无法扣除这种重叠，所以 0 未满足需求只表示当前模拟模型的结果，不能解释为真实网络有足够运力。
