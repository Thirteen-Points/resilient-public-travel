# VERIFICATION — 东铁 10,000 人沙盒

- 运行目录：`sim_cpp/out/run1`
- 重复运行：`sim_cpp/out/run1_repeat`
- 输入：`D:/Competition/Hackathon2026SepOct/sim_cpp/data/sim_input.json`
- 输入 SHA256：`c6aaef9cb197173b264f6eed2e99708ad7e798ec13b85ea951fb6f01636cb4f1`
- 人口哈希：`5d713f3e1575661a`

## 检查结果

| 检查 | 结果 |
|---|---|
| 输入哈希（sidecar） | PASS |
| 人口 10,000 / 五类各 2,000 | PASS |
| served + censored = 10,000 | PASS |
| 物理 95% 上限 / 无超载 | PASS |
| 站台事件复算（峰值 / 人·分） | PASS |
| 到达延误按 passenger id 配对复算 | PASS |
| Bucket 容量账本 | PASS |
| 确定性（两次运行哈希一致） | PASS |

## 关键复算值

| 组 | served | censored | 平均延误 min | P95 min | 最大 min | denied | forced | 站台人·分 | 峰值列车 LF | 峰值车辆 LF |
|---|---|---|---|---|---|---|---|---|---|---|
| A | 10000 | 0 | 0.00 | 0.00 | 0.00 | 0 | 0 | 29759.8 | 23.8% | 23.8% |
| B | 10000 | 0 | 9.37 | 18.00 | 30.00 | 0 | 0 | 58252.7 | 36.2% | 54.6% |
| C | 10000 | 0 | 9.50 | 17.00 | 60.00 | 0 | 633 | 65375.3 | 34.8% | 34.8% |

## 断言

**PASS** — 所有断言通过。

## 复算口径

- 站台峰值/人·分：由 `station_waiting_events.csv` 的 delta 逐事件积分；初始 13:00 为空，17:00 清空。
- 到达延误：B/C 的 `arrival_exc_s` 减去 A 中同一 `passenger_id` 的到达时间，除以 60。
- 物理容量：每车 `floor(0.95 × capacity_per_vehicle)`；`line_loads.csv` 的 `max_onboard` 不得超过该值。
- Bucket：`bucket_allocations.csv` 中 `assigned` 行才消耗 route/segment bucket；`fallback` 不计入 bucket 容量。
- 确定性：两次运行的 `manifest.json` 文件 SHA256 映射完全一致。
