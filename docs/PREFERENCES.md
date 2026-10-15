# 首次访问出行偏好引导

首次访问根页时，在现有规划页上方打开原生模态 `dialog`。桌面弹窗居中并保留四周空间；背景可见、虚化并设为 `inert`。手机使用上下排列及弹窗内部滚动。完成后再次访问直接进入规划页。

引导界面使用全英文文案，模态框声明 `lang="en"`，品牌沿用规划页的 `rr.` 字标。题目、选项、进度、画像说明、可访问名称及导出 JSON 解释均使用英文；维度 ID、存储 key 和评分规则保持不变。主要入口为 `Let's begin`，摘要提供 `Finish` 与 `Explore more`，完成后通过 `Plan my journey` 进入规划页。

`?view=preferences` 可主动打开引导；`?view=planner` 直接进入规划页，不创建问卷存储或事件。`?data=seed` 保留固定演示数据模式，可与两个入口组合使用。关闭引导保留进度，下次打开可以继续。

## 问卷与权重

前三题按时间、换乘、步行顺序采集，第三题后显示九维摘要，可直接完成或继续完善。附加六题依次覆盖票价、舒适度、可靠性、碳排放、信息新鲜度、无障碍。

每题三个选项分别映射为该维度的 `0.95 / 0.5 / 0.15` 重视分值；跳过和未采集均使用中性先验 `0.5`。若一个维度收到多个选项证据，先取分值平均，再将全部九维原始分值除以总和，得到和为 `1` 的权重。显示百分比使用最大余数法，整数百分比合计为 `100%`。

每个维度保留 `evidence`：采集状态 `collected / skipped / prior`、原始分值 `raw`、选项文案 `option` 和解释 `source`。跳过与未采集保持可区分，不会被当成明确的低偏好。

`useReducer` 维护欢迎、答题、摘要、完成四种阶段。选择后短暂等待再自动推进；回退、跳过和其他选择会使旧计时器失效。回退保留后续答案，但仅当前题及以前的证据参与画像计算；重新访问后续题时再纳入其影响。刷新恢复进度，不恢复未完成的自动推进计时器。

## 推荐引擎集成

完整九维画像可以导出 JSON。完成后的画像同时用于规划页，`walking` 映射为后端 `walk`，`fare` 映射为 `price`；`time / transfers / comfort / reliability / carbon / freshness` 保留原名。这八个后端支持的权重重新归一化，作为路线查询的 `profile.weights`。已有路线评分公式与数据来源不变。

`accessibility` 保留在九维画像和导出文件中。它尚不是后端数值评分项，因此不会进入八维评分权重，也不会自动把用户判定为轮椅使用者、开启无障碍硬约束或替代规划页中明确设置的行动能力限制。画像中的百分比表示偏好分配，不表示路线实际表现、通道可用率或数据置信度。

## 存储与事件

- `rr.preferences.v2`：版本、阶段、题目队列、游标、答案及导航状态。
- `rr.weight-profile.v2`：完成后的九维权重、逐维证据、采集数量与当前有效答案。
- `rr.preference-events.v2`：最近 100 条事件，含事件名和 ISO 时间。
- 浏览器事件 `rr:preference-event`：同步提供相同事件数据，默认不上传。

事件覆盖开始 `start`、答题 `answer`、跳过 `skip`、回退 `back`、继续 `continue`、完成 `complete` 和重置 `reset`。存储不可用或数据损坏时仍可作答；恢复时校验版本、队列、答案及阶段，拒绝不一致数据。

## 动效与可访问性

GSAP 统一编排弹窗入场、问题切换、画像更新与九种地图反馈。监听 `prefers-reduced-motion`，减少位移和连续运动。原生模态层配合背景 `inert`、键盘焦点管理、方向键单选、可见焦点和 `aria-live` 通知。

## 验证

```powershell
cd frontend
npm test
npm run build
cd ..
$env:M2_PLAYWRIGHT = '<playwright 模块路径>'
node tests/browser/preferences.e2e.cjs
```

浏览器脚本默认启动独立端口的 Vite 开发服务器。设置 `PREFERENCE_PRODUCTION=true` 使用已经构建的 Vite preview；设置 `PREFERENCE_BASE_URL` 使用已有服务器或本次 PR 的 Pages 预览。测试以 `data=seed` 隔离规划页 API，字体和地理底图请求使用确定性测试响应，实际问卷脚本和本地数据不替换。

安装在 Playwright 运行时旁的 `axe-core` 会自动启用 WCAG AA 检查；CI 固定安装 `axe-core@4.10.3` 并设置 `PREFERENCE_REQUIRE_AXE=true`，缺少审计工具即失败。截图、布局、审计结果、导出画像和事件断言结果写入忽略目录 `.cache/preferences-browser/`。

浏览器验收覆盖全英文可见文案与可访问名称、`rr.` 品牌一致性、桌面居中模态、背景不可交互、核心和附加题、自动推进取消、跳过和回退保留、刷新、九维归一化、百分比总和、英文导出、埋点、完成后回访、显式入口，以及 320 / 390 / 768 px 与减少动态效果模式。原有规划页回归显式使用 `view=planner`，保持其存储为空和管理员凭据隔离断言。

## PR 与部署检查

Cloudflare Pages 根据 Git 分支生成预览；生产分支为 `main`。以 PR 最新提交的 `Cloudflare Pages` check 和预览实际运行结果核对部署，不将旧提交或生产站点的成功状态作为新功能部署证据。`Administrator bundle` 与完整 P3/P4 回归同样需要在最新提交通过。

后端 CORS 目前只允许生产 Pages origin，PR 预览中的问卷可以完成，但预览直接调用生产 API 可能被限制。引导验收使用固定演示模式；不为预览改成通配 CORS。生产可用性和后端部署版本仍应分别核对 `/build-info.json`、`/api/health/deep` 与 `/api/meta`。
