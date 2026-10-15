# 首次出行偏好引导

首次访问 `/` 显示引导；已完成用户回到规划页。`?view=preferences` 可随时查看和完善画像，`?view=planner` 直接进入原有规划页。引导独立于 API，可在后端暂不可用时完整作答。

核心题固定策略性覆盖时间、换乘、可靠性，分别了解效率、旅程负担和不确定性。第三题后可保存，或进入自选题库，补充步行、票价、舒适、碳排放、信息新鲜度及无障碍。

## 权重与历史

选项重视分值为 3.6 / 1.8 / 0.6。未采集或跳过的核心维度使用先验 1，扩展维度使用 0.45。所有九维统一除以总分；百分比采用最大余数法，显示总和为 100%。画像逐维标明 `collected`、`skipped` 或 `prior`，并保留原始分值与选项说明。

`useReducer` 管理欢迎、答题、摘要、题库、完成五种状态。选择后 750ms 切题，修改、回退、跳过会使旧的定时器失效。回退保留后续答案，但只计入当前题及之前的证据；重新走到后续题后恢复其影响。刷新保留进度，不恢复旧定时器。

## 本地存储与集成

- `rr.preferences.v1`：版本、阶段、题目队列、游标与答案。
- `rr.weight-profile.v1`：九维 `weights`、逐维 `evidence`、采集数量、答案、完成状态和更新时间。
- `rr.preference-events.v1`：最近 100 条开始、答题、跳过、回退、继续、完成、导出事件。
- `rr:preference-event`：同名浏览器事件，可接入现有埋点监听器；默认不上传。

用户可下载 JSON 画像。存储不可用时仍可作答和导出，页面提示进度无法保存。已完成画像由 `loadPlannerProfile` 加载到规划页，映射 `walking → walk`、`fare → price`，八个现有评分维度重新归一化并送入路线引擎；切换 preset 后仍可使用原有偏好编辑器。完整九维保留在画像与导出文件中。无障碍目前不属于后端评分维度，其权重是软偏好，不自动推断轮椅身份或替代规划页的硬约束。

## 验证

```powershell
cd frontend
npm test
npm run build
cd ..
$env:M2_PLAYWRIGHT = '<已安装的 playwright 模块路径>'
node tests/browser/preferences.e2e.cjs
```

Playwright 运行时旁需安装 `axe-core@4.10.3`（CI 使用同一个隔离依赖目录）。浏览器脚本启动已构建的 Vite preview；也可通过 `PREFERENCES_WEB_URL` 指向运行中的页面。验证五个阶段的 WCAG AA 规则，并将截图及结果写入忽略目录 `.cache/preferences-browser/`。原有规划回归使用 `?view=planner`，不依赖首次引导状态。
