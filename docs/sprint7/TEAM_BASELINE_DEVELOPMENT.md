# Sprint 7 团队开发候选说明

状态：待 Owner 审查，非发布版本，非全部技术合同冻结。不是新产品规格。

## 可用代码及边界

- Music Library owner-scoped 基础服务、MusicCardV1 schema 与合成 DTO fixture 已包含；真实 Library API 尚未实现。
- My 历史和收藏仍为 Mock；adapter 默认关闭，历史 music_id Player 导航未启用。
- PF-1A 已关闭自动学习写入和新 Diagnosis/Prescription 对旧偏好快照的消费；历史快照只读。
- SQLite/MySQL 迁移到 0010；0012/0013、共享 owner/context/state、反馈删除和 clear 尚待实施，不得自行抢占迁移编号。
- Stream 权限和 retention 尚未验收；列表 availability 不能代替 stream 请求时再次验证。
- 不得改写历史 Diagnosis/Prescription、GenerationSpec、MusicAsset 和 checksum。

## 合同与任务依据

MusicCardV1 类型见 `backend/app/schemas/v3/music_library.py`，对照
`tests/api/v3/fixtures/music_card_v1.json` 与 `frontend/common/music-card-v1-preview-fixture.js`。
未知实际时长为 null；收藏不代表长期偏好；context 只含本人合法关联，不推断患者或聆听者身份。
Mock ready 不证明任何真实音频存在。

四份 R2-A 草案不随本开发包分发。本说明是本轮公开的最小接口接入依据，不代表草案全部冻结；未定项由 Integration 在开发相应功能前裁定，不阻止无依赖部分开发。
已批准游客优先及本地用户名密码；TTL、密码参数、Android 安全存储、H5 Cookie/CSRF 为实施 Gate。
M1 不启用长期偏好学习、不公开分享；原图访问先核实现行合法保留政策。

### 已实现的 MusicCardV1

| 字段 | 类型 / 语义 |
|---|---|
| music_id | 非空字符串，最多 64 字符；去重标识 |
| source_type | generated / matched / comfort_audio |
| default_title / display_title | 非空纯文本；不得使用 HTML 渲染 |
| user_title | string 或 null；当前基础服务固定 null，没有私有标题写入 |
| metadata_version | 非负整数；当前为 0，尚未实现标题 CAS |
| playable_created_at | UTC 时间；本人合法任务完成时间的最小值，无完成时间则用资产创建时间；不是反馈来源选择 |
| last_played_at | 时间或 null；当前固定 null，不伪造播放事件 |
| activity_at | 当前等于 playable_created_at；后续播放活动、排序及 cursor 规则须由 INT-2 统一 |
| duration_seconds | 正整数或 null；当前历史服务因缺测量来源返回 null，不复制目标生成时长 |
| availability | ready / expired / quarantined / deleted / missing |
| is_favorite | boolean；独立于偏好学习与资源权限 |
| primary_instrument_code | dizi / guqin / guzheng / sheng / xiao / pipa / unknown |
| primary_instrument_origin | persisted / legacy_single / unknown；当前只识别合法单乐器旧数据，否则 unknown |
| source_summary | kind: uploaded_documents / questionnaire / none / unknown；availability: available / unavailable / unknown；context_count: 非负整数 |

后端当前导出 `list_owner_music_history(db, internal_user_pk=..., now=...)`，返回
`OwnerMusicHistoryItem(card, context_ids)` 列表；context_ids 不在公开 MusicCardV1 内。
按 activity_at、music_id 降序。后续分页不能仅凭客户端传入 owner 标识授予访问。

### Adapter 预留 API，不是已上线接口

以下来自 `frontend/common/music-library-api.js`，是待 Backend/Integration 接线验收的接口意图；当前不可用于真实联调。

| 操作 | 路径与请求 |
|---|---|
| 历史 | GET /api/v3/me/music-assets?limit=20&cursor=... |
| 收藏列表 | GET /api/v3/me/music-favorites?limit=20&cursor=... |
| 详情 | GET /api/v3/music/assets/{music_id}?context_id=...，context 可选不等于可静默选择来源 |
| 标题 | PATCH /api/v3/music/assets/{music_id}/title，user_title、expected_version |
| 播放 | POST /api/v3/music/assets/{music_id}/playback-events，event_id、event_type=play_started、source_context_id |
| 收藏 | PUT /api/v3/favorites，music_ref；DELETE /api/v3/favorites/{music_id} |

adapter limit 接受整数 1～50；cursor 视为不透明值并编码。当前仅要求响应有 data，或 error.code；
尚无完整服务端分页 envelope、cursor 签名/epoch、MusicDetail DTO、CAS 冲突码和幂等持久化实现，Frontend 不得自行补字段或宣称冻结。
adapter 本地错误为 FEATURE_NOT_READY、IDENTITY_REQUIRED、OWNER_CHANGED、INVALID_RESPONSE、INVALID_LIMIT；服务端错误码透传。
默认 enabled=false，不创建身份或长期凭据，不触发生成；owner 切换后拒绝迟到响应。它不是服务端鉴权机制。

### owner / context / Stream 边界

- Library 成员资格来自明确本人 asset owner 或本人 succeeded/matched_fallback 任务。NULL owner、Favorite、失败/取消任务单独均不足以授权。
- 按 music_id 去重，只保留本人合法任务 context；多 context 不自动选最早或最新用于来源查看/反馈，不推断病历主体或实际聆听者。
- 无 context 可展示合法资产卡片；需要来源的操作必须在服务端验证 context 属于当前 owner 且关联当前资产。多来源未选择时保持该操作关闭，不编造关联。
- Library ready 只表示查询时在受控媒体范围内验证到可读取的合法本地文件。其他/远程 locator 无法证明时 fail-closed。
- 实际 stream 尚须独立完成 owner、catalog 合法授权、retention、状态及文件校验；不得依据 NULL owner 推定公开访问，也不得以本次 Library 检查替代。
- Stream Gate 与真实 API 未验收前，历史 Player 导航保持关闭；不新增第二个播放器。

### PF-1A 与 PF-1B

PF-1A 已实现自动学习写入关闭、新生成消费旧偏好快照关闭；历史偏好只读。
PF-1B 尚未实现逐条授权、列表、删除 tombstone、clear、epoch/CAS 和旧接口/缓存失效。
后续授权默认 false，有效政策版本由服务端验证并记录；旧反馈不得追溯授权，新反馈即使授权 M1 也不自动学习。
删除及 clear 不得被 replay、旧版本指针或并发计算复活；不能修改已有音乐历史快照。

### 文件所有权与未定项

- Backend：music library / identity / music 模型与服务、相关 schema/测试；stream 变更须按 Issue #151 的授权和接口裁定处理。
- Frontend：My、原 Player、反馈 UI、common adapter/state 和对应 Node 测试；不得绕过真实 API/stream Gate。
- Preference：feedback 模型、feedback_service/feedback_router 及后续授权/删除测试；不建立第二套 owner state。
- Evidence：独立审计文档及合成反事实测试；无生产医学规则/算法写权限。
- Integration：共享模型导出、main.py 路由接线、frontend/pages.json、成对迁移、跨模块合同 fixture 与集成验收；其他成员先提需求，不抢写共享文件。
- 多 lane 触及同一既有文件时先由 Integration 明确 hunk/单一写入责任，不整文件覆盖。

待决或待工程验证：INT-2 共享 state/epoch/CAS/游标和完整 API DTO；账号安全参数与依赖；
原图保留/删除政策；无法证明的旧 catalog 授权；长期偏好 M2 与医学规则裁定。
这些 Gate 限制相应功能实施/联调，不要求为建立代码开发分支先完成完整 App。

| 工作流 | 负责人 | Issue | 依赖 |
|---|---|---|---|
| INT-2 | Owner / Integration | #150 | 共享模型、迁移、最终集成 |
| BE-2B | 蔡子鑫 | #151 | INT-2、stream 权限裁定 |
| FE-2B | 彭翔 | #153 | Backend API 与 stream Gate；此前只做 Mock/接口准备 |
| PF-1B | 钟睿宸 | #152 | INT-2 owner/context/state |
| R1/R2-B | 肖宇翔 | #154 | 合成审计、医学裁定，不改核心规则 |

Owner 发布并公布精确基线后才创建开发分支；不得以当前 GitHub main 假装拥有 W2。
PR 关联 Issue，列明修改、实际测试命令和数量、依赖、风险及 NOT RUN；不直接向 main 提交。

## 环境与验证

- Python 版本见 pyproject.toml；后端运行依赖见 requirements.txt。不能只安装 pyproject 就认为后端依赖完整。
- 测试另需 pytest、httpx；完整锁定测试依赖尚未在全新环境验证。
- 前端依赖见 frontend/package.json。Node 测试逐文件独立进程执行，不以共享状态单进程运行替代。
- H5 缺 node_modules 时为 NOT RUN，不自动联网安装。
- 只用合成资料、临时音频、隔离数据库及 Fake Provider；禁止生产数据与真实 Provider。
- 本机离线防护及日志保存在 Git 管理目录，团队可分发防护包尚待准备；普通 pytest 不等于受控离线 Gate。

## 受限资源 Gate

未确认许可的图片、WAV 和文献 Corpus 不分发；保留原测试及有效断言。

- UI 素材影响完整视觉验收，不阻止纯状态/DTO 开发。
- Phase-I 收集时读取指定 60.8816 秒 WAV，缺失阻止该文件正常收集。合成音频可验证协议，不能证明原内容或许可。
- 产品恢复测试校验指定设计图片哈希，不能用合成图片冒充原批准设计。
- Corpus 测试核验指定医学版本、13 个来源和校验和；合成 Corpus 不能冒充医学批准 Corpus。
- 完整 App、真实知识检索和设计验收仍为 BLOCKED_BY_RESTRICTED_RESOURCES。
- README 历史 MIT 文案不等于所有第三方资源许可；main 既有两张 PNG 也未完成独立权利核验。
