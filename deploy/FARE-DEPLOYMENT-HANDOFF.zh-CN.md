# 票价数据库：Render 部署交接

交接日期：2026-10-11。仓库：<https://github.com/Thirteen-Points/resilient-public-travel>。

发布分支：`codex/fare-database`，基于当时最新 `main` 的
`7d658237e432d1a2a38ae95fc300b9331db216a4`，只合入票价修复。
原工作区 `ZYC-P4` 中其他出行方式、地图和离线演示改动不在这次发布范围。
发布分支提交后，通过对应 Pull Request 合并，避免直接上传整个本地目录。

## 当前状态和交付内容

- 线上前端：<https://resilient-public-travel.pages.dev/>。
- 线上后端：<https://resilient-public-travel-api.onrender.com>。
- 2026-10-11 检查时，后端 `/api/meta` 返回上述 `7d658…` 版本；前端 Pages 生产部署也对应这个提交。
- 代码已经完成本地测试和生产构建；本次票价修复尚未部署生产，完整官方数据库尚未导入 Render。
- 当前协作者可以操作 Cloudflare；Render 属于接手者账号，需要接手者完成后台和 Shell 操作。

原问题是 SeedDataAdapter 把所有地铁票价设为统一的 HK$12.50。
修复后，每次路线查询读取持久化 SQLite 票价和数据库版本，按实际乘车起终点计费；更新 SQL 价格自动失效旧路线缓存。
港铁站内换线合并成一张入站/出站票，公交按方向和分段收费，天星小轮按平日/周末或公众假期、上下层收费。
查不到票价返回数据不可用，不能回退为 HK$12.50。

首次启动会用 `data/network/fares.json` 初始化空库，覆盖当前规划图；它只是启动数据。
要满足完整数据库交付，必须在 Render Shell 执行下文官方导入。
本地已验证的官方导入包含 9,216 条港铁 OD、777,319 条公交分段、1,622 条公交全程和 4 条渡轮费率，共 788,161 条价格。
完整 SQLite 约 125 MB，不进入 Git，也不复制其他业务数据库。
目前轮渡范围为中环↔尖沙咀；并未覆盖全港全部轮渡运营商。

发布版本本地验证：后端及集成全套 529 个测试通过（另有 278 个 subtests），
前端 103 个测试通过，TypeScript/Vite 生产构建通过，四份契约种子校验及部署 preflight 通过。
这些结果来自 Windows 本地发布检出，不代表 GitHub CI、浏览器线上验收或 Render 持久磁盘已经通过。

## 1. 在现有服务部署前记录配置和备份

在 Render Dashboard 打开现有 `resilient-public-travel-api` 服务，核实它关联的仓库、部署分支、当前提交、Start Command、环境变量名称和磁盘配置。
`render.yaml` 预期使用一个实例，磁盘挂载点为：

```text
/opt/render/project/src/backend/app/data
```

这是仓库配置，尚未通过 Render 账号核实实际磁盘。
如果实际没有持久磁盘，应先由所有者配置存储并决定相应费用，再发布需要持久化的数据库版本。
保留已有 `DB_PATH`、`FARE_DB_PATH`（若有）、管理员凭据和 `ADMIN_ENCRYPTION_KEY`。
不要删除服务、磁盘或业务数据，不要把密钥放进前端 `VITE_*` 变量。

在服务 Shell 切到仓库根目录，使用 SQLite backup API 为现有数据库备份；下面命令只创建备份，不覆盖数据库。
备份写在持久磁盘的独立时间目录；记录输出，并使用平台提供的安全方式保留到独立恢复位置。

```bash
python - <<'PY'
import hashlib, os, sqlite3
from datetime import datetime, timezone
from pathlib import Path

events = Path(os.environ.get('DB_PATH', 'backend/app/data/events.sqlite3')).resolve()
fares = Path(os.environ.get('FARE_DB_PATH', str(events.with_name('fares.sqlite3')))).resolve()
stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
folder = events.parent / 'backups' / ('before-fares-' + stamp)
folder.mkdir(parents=True, exist_ok=False)
paths = [events, events.with_name('admin.sqlite3'), events.with_name('ai_usage.sqlite3'), fares]
for index, source in enumerate(dict.fromkeys(paths)):
    if not source.is_file():
        print('ABSENT', source.name)
        continue
    target = folder / (str(index) + '-' + source.name)
    with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as src, sqlite3.connect(target) as dst:
        src.backup(dst)
        check = dst.execute('PRAGMA integrity_check').fetchone()[0]
    if check != 'ok':
        raise RuntimeError((source.name, check))
    with target.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    print('BACKUP', target, digest, check)
PY
```

每个文件为独立一致性备份；如果需要跨数据库同一时间的恢复点，应先暂停业务写入。
记录旧部署 ID 和 SHA，以便回滚代码。

## 2. 发布代码

查看 `codex/fare-database` 对应 PR 和本地验证结果，接手者合并到最新 `main`。
如果 main 已有新提交，先合并最新 main、解决冲突并重新跑受影响测试，保留新功能。
现有 Pages 项目生产分支为 main，GitHub 自动部署已开启。
Render 端核实自动部署配置；未自动触发时，使用 Manual Deploy 部署合并后的准确提交。

现有后端构建和启动命令可继续使用：

```bash
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --host 0.0.0.0 --port "$PORT"
```

不需要把官方导入放进 Build Command：Render 的运行磁盘应在运行时 Shell 访问。
保持前端 `VITE_API_BASE_URL=https://resilient-public-travel-api.onrender.com`，
后端 `CORS_ALLOWED_ORIGINS=https://resilient-public-travel.pages.dev`。
前端和后端自动部署可能先后完成；以二者实际部署完成和接口验收为交付条件。

## 3. 在 Render Shell 导入完整官方票价库

确认 Shell 使用本次已部署代码，从仓库根目录运行：

```bash
python -m scripts.refresh_fares --download
```

这会下载港铁票价/车站 CSV、运输署公交线路/停站/分段 XML、天星小轮 XLSX，
然后在一个事务中导入当前官方数据并更新公交停站序号映射。
默认数据库为 `fares.sqlite3`，与 `DB_PATH` 指向的 events 数据库同目录；显式 `FARE_DB_PATH` 优先。
命令成功会打印导入数量和真实 SQL 库状态。
约 150 MB 的公交分段 XML 会流式读取，仍需预留源文件、数据库及事务 WAL 的空间。

若下载被网络或来源站点阻断，保留错误并先解决访问；不要只导入启动 JSON 后宣布完整导入成功。
重试可以再次执行上述命令；失败事务不会替换现有可用价格。
如已安全下载六个官方文件，也可使用：

```bash
python -m scripts.refresh_fares --source-dir /path/to/fare-sources
```

源文件名和来源 URL 见 [FARES.md](FARES.md)。导入成功后不需要重启应用。
此版本没有定期自动刷新任务；日后官方调价需要再次运行导入命令。

## 4. 线上验收

### 版本、健康和完整库

```bash
curl -fsS https://resilient-public-travel-api.onrender.com/api/meta
curl -fsS https://resilient-public-travel-api.onrender.com/api/health/deep
curl -fsS https://resilient-public-travel-api.onrender.com/api/fares/status
```

记录部署 ID、合并 SHA、时间和 HTTP 状态。
`/api/meta` 的 `build.commit_sha` 必须等于本次实际合并部署提交，深度健康应成功。
`/api/fares/status` 必须报告 `storage: sqlite`，且完整库的 MTR/BUS 数量不能仍只有启动图的 256/10 条。
本地来源快照对应 MTR=9,216、BUS=778,941、FERRY=4；官方数据若更新，以本次成功导入日志为准。
检查六个来源的 URL、SHA-256 和导入时间；不要对外发布数据库文件或私密配置。

### 存储价格和路线计价

```bash
curl -fsSG https://resilient-public-travel-api.onrender.com/api/fares/lookup \
  --data-urlencode 'service_id=mtr:octopus' --data-urlencode 'origin=TAW' \
  --data-urlencode 'destination=ADM' --data-urlencode 'payment=octopus' \
  --data-urlencode 'at=2026-10-12T08:20:00+08:00'

curl -fsSG https://resilient-public-travel-api.onrender.com/api/fares/lookup \
  --data-urlencode 'service_id=bus:1051' --data-urlencode 'origin=20' \
  --data-urlencode 'destination=25' --data-urlencode 'direction=1' \
  --data-urlencode 'at=2026-10-12T08:20:00+08:00'

curl -fsSG https://resilient-public-travel-api.onrender.com/api/fares/lookup \
  --data-urlencode 'service_id=FERRY_TST_CEN' --data-urlencode 'origin=*' \
  --data-urlencode 'destination=*' --data-urlencode 'day_type=weekday' \
  --data-urlencode 'deck=upper' --data-urlencode 'at=2026-10-12T08:20:00+08:00'

curl -fsS https://resilient-public-travel-api.onrender.com/api/routes/query \
  -H 'Content-Type: application/json' \
  -d '{"origin":"TAW","destination":"ADM","depart_at":"2026-10-12T08:20:00+08:00"}'
```

已验证的成人价格依次为 HK$17.10（大围→金钟港铁）、HK$12.20（182 红隧→金钟分段）、HK$5.00（平日渡轮上层）。
可补查未在规划图内的港铁 CHW→TUC=HK$27.90，以证明完整 OD 库已导入。
路线结果的纯港铁方案应为 HK$17.10；不同模式组合按实际票段累计，不能全部相同为 HK$12.50。
核实每条路线的各段 `fare_hkd` 之和等于总价，港铁换线不重复扣款。
网页刷新后检查总价、详情票段，以及 Compare 等已有页面仍能使用。
路线接口仍应保留既有 `X-Route-Snapshot` 响应头。

### 持久性

记录导入后的 `/api/fares/status` 数量、revision 和来源校验值，重启或再次部署同一代码并重复读取。
未进行新的导入或价格更新时，revision、数量和来源应保持；同时验证原业务健康。
不能把数据库路径存在或本地测试通过当作线上持久性证据。

## 5. 回滚和交接完成条件

若本次代码导致健康或路线错误，回滚到记录的旧部署提交，保留磁盘和现有数据库。
此票价变更新增独立数据库，代码回滚不要求还原 events/admin/ai_usage；不要因此丢失新提交的业务记录。
数据库恢复只在确认数据问题和恢复点后进行，并先保存失败状态。

接手者回传：后端部署 ID/提交、Pages 部署 ID/提交、导入日志、status 摘要、三项价格和实际路线/网页证据、重启后的持久性结果。
全部完成后才能标记“已部署且完整官方票价库上线”。

更多 SQL 表结构、有效期与计价范围见 [FARES.md](FARES.md)。
