# B 工作流：团队待确认事项

> 本页由 B 在每项任务完成后更新，只记录会影响 A / B / C 接口或契约的未决事项。

## T2.1 / T2.2（2026-09-22）

- `Event.line` 示例与种子数据使用 `ERL`，但线路枚举写成 `ERL_E` / `ERL_W`；需在契约冻结前统一。
- `event.seed.json` 的 Event 含契约未定义的 `ui_state`，部分 Signal 又缺少示例中的 `author_hint` / `raw_url`；需决定这些字段是契约字段还是仅前端 fixture。
- T2.1 任务卡写“增删改查”，但事件生命周期已有 `expired` / `rejected`；需确认是否禁止硬删除以保留审计记录。
- `Signal.source_type` 尚无正式枚举；T2.2 暂用种子数据已有的 `official`。
- Signal 没有独立的“警告生效/取消”字段；T2.2 暂时把状态写进 `signal_id` 与 `raw_text`。
- HKO 最近成功快照目前只存在内存中；需确认后续是否由事件服务持久化，避免服务重启后重复发出当前警告。
