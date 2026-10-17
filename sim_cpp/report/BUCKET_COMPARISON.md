# BUCKET_COMPARISON — B（bucket）vs C（即时最快）

> 数据：`sim_cpp/out/run1`；验证：`sim_cpp/report/VERIFICATION.md`（PASS）。所有数字可由 `B/bucket_allocations.csv`、`B|C/passengers.csv`、`line_loads.csv` 复算。

## 1. 口径：两种容量不能混用

| 口径 | 数值 | 用途 |
|---|---:|---|
| route supply planning cap（rail-only） | 3,400 人/h | route bucket + 共享有向路段 bucket 的规划上限 |
| route supply planning cap（bus-dependent） | 460 人/h | 任何含 BUS/MINIBUS/FERRY 的路线 |
| physical 95% per train（ERL） | 2,702 人/车 | 事件仿真的登乘上限 |
| physical 95% per train（KTL/TWL/TML） | 2,375 人/车 | 事件仿真的登乘上限 |
| physical 95% per bus（BUS_182） | 130 人/车 | 事件仿真的登乘上限 |

本报告只用第一种口径（3,400/460）做 bucket 分配；第二种（95%）只做列车登乘。两者没有混用。bucket 满不等于列车满：ERL 的物理吞吐约 27,020 人/h，3,400/h 只有约 12.6%，所以 bucket 会先绑定，而列车仍可能有大量余量。

## 2. 分配账本

| 项目 | 数值 |
|---|---:|
| assigned | 9314 |
| fallback | 686 |
| protected assigned | 4000 |
| protected fallback | 0 |
| no route | 0 |
| 至少撞到一次 route cap | 1929 |
| 至少撞到一次 segment cap | 231 |
| 最大额外时间 | 13.0 min |

| 窗口 | assigned | fallback | 主要绑定资源 |
|---|---:|---:|---|
| 13:00–14:00 | 4388 | 266 | ERL 直达 route bucket 3,400/3,400；ERL KOT→MKK / MKK→HUH 3,400/3,400 |
| 14:00–15:00 | 4926 | 420 | KTL+TWL+ERL route bucket 3,400/3,400；KTL KOT→PRE / TWL 3,400/3,400 |

**窗口 0**：ERL 直达 bucket 先满，988 人转到 KTL+TWL+ERL。其中 633 人正好是 C 的 forced 集合；其余 355 人是因为 ERL 规划 cap 满而被提前分流的普通乘客。后者不是安全所必需，是 bucket cap 的直接副作用。另有 266 人 fallback 到 ERL 直达（不消耗 bucket），窗口 0 实际 ERL 直达 3,666 人，超过 3,400 的 bucket cap。
**窗口 1**：KTL+TWL+ERL bucket 满后，420 人 fallback（两个窗口合计 686 人）。fallback 不消耗 bucket，仍然走个人最快路线（同一条 KTL+TWL+ERL）；因此这 420 人没有真正被“分散”，只是被排除在 bucket 账本之外。这是本场景 bucket 最大的结构性限制。
**71 名 BUS_182 乘客**：他们的最快路线是 KTL+TWL+ERL（约 31.7 min），bus 路线约 44.7 min，extra 13.0 min，仍在 15 min 上限内；bucket 把他们分到 bus，降低了 KTL 列车负载，但把 BUS_182 的峰值载客率推到 54.6%（71/130）。这 71 人是 B 的最大延误（30 min）来源。

## 3. B vs C：延误、尾部、拒载、集中度、步行

| 指标 | B | C | 差异 / 判断 |
|---|---:|---:|---|
| 平均到达延误 min | 9.37 | 9.50 | B 低 0.13，幅度很小 |
| P95 到达延误 min | 18 | 17 | B 高 1 min，B 输 |
| 最大到达延误 min | 30 | 60 | B 低 30 min，B 赢 |
| affected (>1 min) | 5876 (58.8%) | 5701 (57.0%) | B 更广，B 输 |
| >15 min 比例 | 42.4% | 42.7% | B 略低 |
| >30 min 比例 | 0.0% | 1.3% | B 赢 |
| >45 min 比例 | 0.0% | 1.3% | B 赢 |
| forced alight | 0 | 633 | B 赢 |
| denied boardings | 0 | 0 | 平（均 0） |
| replans | 0 | 813 | B 赢 |
| 平均步行 m | 2.8 | 16.8 | B 赢 |
| 站台等待 人·分 | 58253 | 65375 | B 低 7,122 |
| KOT 峰值 | 501 | 633 | B 低 132 |
| HUH 峰值 | 599 | 633 | B 低 34；B 峰值在 15:03，C 在 14:04 |
| HUH 人·分 | 2488 | 9370 | B 低 6,883 |
| 路线 HHI | 0.406 | 0.500 | B 更低（更分散） |
| 最大路线份额 | 48.1% | 51.1% | B 低 3.0 pp |
| 峰值列车载客率 | 36.2% | 34.8% | B 高 1.3 pp，B 输 |
| 峰值车辆载客率 | 54.6% | 34.8% | B 高 19.8 pp（BUS_182），B 输 |

### 3.1 延误
总体均值 B 只低 0.13 min，不能称为显著改善。更值得注意的是分布：B 的 P95 反而高 1 min，affected 比例高 1.8 pp；但 B 的最大延误低 30 min，>30/>45 为 0。这是“压缩最坏尾部、扩大轻微绕行”的策略，而不是整体提速。
按画像拆开，B 的收益完全集中在 protected：轮椅平均 8.51 vs 11.28 min，P95 17 vs 60；长者 8.85 vs 9.50，P95 17 vs 29。普通群体的平均延误反而高 0.85–0.99 min，P95 高 7 min。所以 bucket 是一个 **distributional policy**，不是 Pareto improvement。

### 3.2 拒载
三组 denied 都是 0。峰值列车载客率 B 36.2%、C 34.8%，95% 上限从未绑定。因此本场景不能证明 bucket 在拒载上赢 C；能说的只是：在 95% 物理上限下，两者都没有触发拒载，bucket 的 3,400/460 规划 cap 与物理拒载是两件事。

### 3.3 集中度
按路线份额，B 更分散：HHI 0.406 vs 0.500，最大份额 48.1% vs 51.1%。但按峰值车辆载客率，B 更集中：BUS_182 71/130 = 54.6%，C 的最高只有 34.8%。所以“集中度”要说明口径：路线层面 B 赢，单车/单路段峰值层面 C 赢。
列车层面差异很小：B 36.2%（ERL HUH→EXC，977/2,702）vs C 34.8%（ERL ADM→EXC，941/2,702）。B 的 TWL TST→ADM 列车负载比 C 低（468 vs 684），但 KTL KOT→PRE 略高（468 vs 450）；B 还把 997 人送到 ERL HUH→EXC 的 15:00 后服务，抬高了该路段峰值。

### 3.4 步行
B 平均步行 2.8 m，C 为 16.8 m。C 的 400 名 standard forced 乘客在 ETS 下车后步行 420 m 到 TST，贡献了 400×420/10,000 = 16.8 m/人的平均步行；B 通过提前分流避免了 HUH 强制下车，只有 71 名 bus 乘客步行 400 m（约 2.8 m/人）。步行负担的差异与 forced alight 是同一件事的两面。

## 4. 结论

**bucket 没有全面赢 C。** 它在最大延误、forced alight、平均步行、站台等待、HUH 人·分、路线 HHI、KOT/HUH 峰值上赢；在 P95、affected 比例、峰值列车载客率、峰值车辆载客率上输；在 served 和 denied 上平。
**bucket 的核心价值是 protected-first 的尾部保障，而不是容量分散。** 封闭期间只有一条快速轨道绕行，KTL bucket 满后窗口 1 的 420 人（合计 686 人 fallback）回到同一条路线；bucket 无法在 15 min 内把需求分到第二条同等级走廊。B 的 forced=0 主要来自“提前知道封闭窗口、把风险乘客提前改道”，而不是“bucket 把 10,000 人均匀摊开”。
**bucket 也有副作用。** 71 名普通乘客被分到 BUS_182，产生 30 min 最大延误和 54.6% 的巴士峰值载客率；988 人中约 355 人并非风险乘客，却因为 ERL 规划 cap 满而被提前改道；而 fallback 不消耗 bucket，窗口 0 实际 ERL 直达 3,666 人、窗口 1 实际 KTL 3,820 人，均超过 3,400 的名义 cap。如果目标是 P95 或普通群体公平，C 更好；如果目标是避免轮椅/长者在 HUH 长时间滞留，B 更好。
**信息假设是最大限制。** B 预知 14:00–15:00 的计划性封闭，C 不预知；这不是同一信息集。若封闭突发、B 也只能在 14:00 才知道，B 无法提前分流 13:52–14:00 的 633 名风险乘客，其 forced=0 和最大延误优势会大幅缩小。任何“bucket 在真实故障下一定更好”的说法都超出了本实验。

## 5. 复算

`B/bucket_allocations.csv` 的 `assigned` 行才消耗 bucket，`fallback` 行不消耗；`route_bucket_used_after ≤ route_bucket_capacity`、`segment_used_after_max ≤ segment_capacity_min`、`extra_min ≤ 15` 都由 `scripts/verify_cpp_sim.py` 逐行检查。`line_loads.csv` 的 `max_onboard ≤ capacity` 和 `max_load_factor` 也逐行复算。
