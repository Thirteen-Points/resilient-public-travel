# 五来源实际可行性核查

负责人：本任务用户。更新日期：2026-10-03，Asia/Shanghai；10/2 的调查是前一日基线，不替代本轮验证。只使用官方资料和实际响应，不依赖付费采集商或绕过登录。当前没有团队社媒凭据。

| 来源 / 官方资料 | 核查日期 | 可取得的数据 | 搜索方式 | 权限要求 | 调用限制 | 费用情况 | 当前阻塞 | 实际验证结果 |
|---|---|---|---|---|---|---|---|---|
| 小红书：[开放平台](https://open.xiaohongshu.com/)、[小程序官方介绍](https://miniapp.xiaohongshu.com/doc/DC137160) | 2026-10-02 / 03 | 未取得可用于本项目的公开笔记搜索和正文读取能力；登录、分享、笔记发布、电商接口不属于内容搜索 | 没有已验证官方入口 | 内容搜索授权入口未核实；不是仅缺一个普通登录 token | 未核实，不设置臆造额度 | 未核实，未采购第三方服务 | **blocked**：no_verified_public_search_entry | 官方入口页面可读，但未取得可调用的笔记检索接口、真实笔记或入库证据；没有向猜测的 API 发请求 |
| Threads：[官方 Discover Threads](https://www.postman.com/meta/threads/folder/u4wm9lw/discover-threads)、[关键词文档](https://developers.facebook.com/docs/threads/keyword-search/) | 2026-10-02 / 03 | 10/2 Meta 示例展示正文、permalink、timestamp、owner 及引用/转发字段；10/3 具体旧示例页显示 Request not found，须再以现行文档确认 | 官方 `/keyword_search` 示例：q，TOP/RECENT；不以网页逆向代替 API | 用户令牌、threads_basic / threads_keyword_search；公开搜索审批范围须用正式令牌验证 | 开发者文档本轮返回 429；不能将文档访问 429 当成 API 额度。数字额度未取得可复核官方正文，保持未核实 | 未核实，未发生 API 调用费用 | **blocked**：缺令牌、已批准搜索权限和真实调用证据 | 没有 token，未调用内容接口；代码只显示阻塞，不宣称已接通 |
| Instagram：[Meta 官方 API 说明](https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api?entity=request-23987686-ab559ffb-8e2c-4b0a-b43a-5737b6d2f672)、[Business Discovery](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-facebook-login/business-discovery/)、[Hashtag Search](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-facebook-login/hashtag-search/) | 2026-10-02 / 03 | 分开看授权专业账号媒体、其他专业账号发现、标签公开媒体；官方说明不支持普通 consumer 账号的通用读取 | 指定账号 / Business Discovery / 标签入口；没有验证任意正文或全站关键词搜索 | 专业账号和正式令牌；Facebook Login 的关联主页及读取权限按功能核实，公开内容访问资格尚未验证 | 官方集合说明游标分页；标签及其他额度当前未核实。Hashtag 文档返回 429 | 未核实，未发生 API 调用费用 | **blocked**：无账号配置、token、读取资格 | 没有媒体 API 请求或真实入库；不把 Instagram Login 与 Facebook Login 的能力混用 |
| Facebook：[主页帖子](https://developers.facebook.com/docs/pages-api/posts/)、[Page Public Content Access](https://developers.facebook.com/docs/features-reference/page-public-content-access/) | 2026-10-02 / 03 | 拟核查指定公开主页帖子，不能默认可读取所有个人账号帖子 | 指定主页的 posts；不默认全站关键词搜索 | 按管理关系核查 pages_read_engagement、Page token 或非管理主页的 PPCA；具体资格须官方审批和实际请求验证 | 文档返回 429；实际 token / app / page 配额未核实 | 未核实，未发生 API 调用费用 | **blocked**：无 token、主页 ID 和访问资格 | 未执行内容读取，不能以官方文档链接代替接通证据 |
| MTR Mobile：[介绍](https://www.mtr.com.hk/mtrmobile/en/transport/traffic-news/)、[官方交通消息页](https://www.mtr.com.hk/alert/alert_simpletxt_title.html)、[页面脚本](https://www.mtr.com.hk/alert/js/redalert.js)、[robots](https://www.mtr.com.hk/robots.txt) | 2026-10-02 / 03 | 网站公开 `alert.json` 的双语公告、稳定 id、issuedTime（可空）、恢复关联；`ryg_line_status.json` 的当前线路状态 | 读取公开列表，本地关键词过滤；无搜索 / 历史分页 API | 实测匿名 GET；robots 未禁止 `/alert/`。仅使用这两个公开文件，每轮检查 robots；不使用网页配置中的密钥，也不调用私有 Mobile API | 线路资源 refreshInterval=180000 ms；采集器至少 300 秒，来源要求更慢时遵循。公开资源没有文档化配额/SLA | 本轮匿名 GET 无付费步骤；未核实收费政策，不宣称商业免费许可 | 技术读取可用；当前公告没有发布时间，真实 Signal 入库仍未验证 | CLI 实际读取两条官方公告并记录来源状态；缺时间按用户决定跳过。三周期日志和最终入库计数以本轮 evidence 为准 |

## 可追溯真实内容

- `D_332`：国庆黄金周东铁线加密班次，来源 [官方公告页](https://www.mtr.com.hk/alert/alert_simpletxt_title_tc.html#D_332)。`issuedTime=null`；不是延误/停运消息。
- `D_328`：启德东盟杯观赛交通安排，来源 [官方公告页](https://www.mtr.com.hk/alert/alert_simpletxt_title_tc.html#D_328)。`issuedTime=null`。
- 数据入口：[alert.json](https://www.mtr.com.hk/alert/alert.json)、[线路状态](https://www.mtr.com.hk/alert/ryg_line_status.json)。只读请求没有登录或验证码。

`lastBuildDate`、HTTP Last-Modified 是资源构建/修改时间，不是每条公告的发布时间。不能为了 24 小时窗口或验收凑数，把它们当作 issuedTime。正常 green 状态也不生成“恢复服务”的合成正文。

## 范围冲突处理

旧计划“社媒只使用模拟流”的范围已被本任务用户明确扩展；模拟模块继续保留。P3 原有 HKO/MTR ETA 是 Web lifespan 管理的调度，本任务的 `mtr_mobile` 是独立 CLI，来源键不同，不注册到旧 Web scheduler。Signal 的 `real` 仅指实际来源，并不代表事实已经人工核实。公共 Signal schema 和人工发布契约不改变。

四个社媒来源目前只有阻塞描述和适配器边界。仅设置 token 不会启动未验收的社媒调用；取得权限后应另行实现并验证对应来源，不承诺自动解锁。
