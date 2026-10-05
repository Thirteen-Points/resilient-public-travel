# B 本地复验证据

`browser/` 由 `tests/browser/b-p3-no-ai.cjs` 在干净临时 SQLite、`OFFLINE_MODE=true`、`AI_ENABLED=false`、`AI_DISABLE_EXTERNAL=true` 下生成。`result.json` 为最终结果；`history.jsonl` 从脚本增加追加记录后保存每次运行。`query-request/response.json`、`wheelchair-request/response.json`、PNG 截图及 `video/*.webm` 是 Edge 运行产物；同目录执行两轮通过，因此有两段录屏。雨天及无路线画面是受控 API 响应契约测试，非真实天气事件端到端录像。未含密钥或原始异常正文。

在启用追加记录前的试跑曾出现 ffmpeg 缺失、异步响应读取过早、天气夹具未满足发布条件等失败；旧脚本覆盖了 `result.json`，当时的堆栈未完整留存。这是本轮证据缺口，不能把目录描述为包含所有原始失败记录。后续重跑会追加至 `history.jsonl`。

完整命令与结果见 `../report-b.md`。工作区旧 `.cache/b-p3-no-ai/` 保留试跑截图/视频但被 Git 忽略，不是可交付版本证据。
