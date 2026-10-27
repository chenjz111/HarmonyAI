# Guest Music Library — 本轮核对和待验收事项

基线 Draft #174 `1bdbef1`，2026-10-12 产品冻结规格及后续 R1 决策；`1bdbef1` Linux/Windows Hosted CI 成功。实际非生产 Guest USB 开关早已存在，要求 Android App、development、两个明确标志和精确 `http://127.0.0.1:8000`，Registered 组合关闭，正式默认音乐库未开启。

| 用户行为 | 现有证据 | 仍欠缺 |
|---|---|---|
| 原合法游客与重开 | Owner 之前确认标准基座游客和 App 重开；本轮无设备 | 后端重启/密钥稳定、过期与完整新流程真机验证 |
| 未播放历史、收藏、改名、单一 Player | 实际页面脚本、真实 ASGI/SQLite 和用户隔离通过；Owner 之前已确认历史重听 | 本轮 Android 默认入口/多首操作 NOT RUN |
| 播放、暂停、Seek | Owner 之前真机确认 | 本轮返回反馈后实际设备播放、迟到音频事件 NOT RUN |
| 每曲反馈、删除、Clear | 实际页面及真实 ASGI/SQLite；Clear 保留历史，学习 OFF | 提交结果未知后关闭页面原幂等键丢失，可能重复写入；跨页面/进程恢复未解决，不得称完整闭环 |
| 原乐器、标题、历史解释 | 既有来源/权限校验及页面测试；Player 使用受信权威字段 | 真实设备视觉及多来源历史操作 NOT RUN；没有原始资料政策授权 |
| 双游客/网络/迟到数据 | 存储、epoch、API 及页面脚本隔离测试 | 物理断网、401、系统回收与设备行为 NOT RUN |

本轮复现修复：进入反馈页面原先销毁 Controller 导致返回后无法播放；改为暂停并维持卸载销毁。独立审查后为迟到 onPlay 添加播放意图检查，暂停后回调不创建播放证明。反馈结果待确认时表单锁定，重试沿用同一 key/body；删除/Clear 确认期间防并发。Player 两处修改及其精确 SHA 经 Owner 分别批准。上述为脚本及模拟音频验证，不是新的 Android 通过。

隔离旅程原有 WAV 误标 MP3：改用恢复的 `frontend/static/music/jiao-demo.wav`，实际 WAV 字节及 MIME 为 `audio/wav`，隔离库格式/文件名/checksum 一致，WAV 根据帧率测得 60.8816 秒并按整数秒记录 61；现有历史 read model 有意返回未知时长，音频替身模拟时长不代表设备解码。没有调用 Provider。

独立复审发现未知提交关闭页后丢失请求键，服务端按 owner/key 去重而非按播放事件去重。恢复本轮工作后，未受保护的 feedback API 增加进程内 owner/event 隔离的待确认屏障；页面重入不能以新键发送同一事件，原页面只允许原键及原请求快照重试，完整成功 DTO 或明确 epoch 冲突才解除。快照仅随原请求对象保留在内存，未知屏障不写入持久存储。真实 ASGI/SQLite 模拟写入后响应丢失：新页面新键被阻止，原键原请求获得服务端重放。**进程被回收/重启后的未知状态无法恢复或阻止再次提交，仍是验收阻塞**；全局256条上限在极端情况下也可能影响其他身份的可用性。无付费 Provider 的本地验收后端仍需准备；真机步骤及每项非敏感失败证据见 `GUEST_LIBRARY_ANDROID_ACCEPTANCE_20261027.md`。

分享 PD016 暂停，原图 PD013/长期偏好 PD010 保持政策门禁，医学独立签核未替代。本轮没有启动手机、生产迁移、付费 Provider、正式 Live Flag、部署或 Merge。

验证记录：Android-context 和普通音乐、native account、H5 account 的真实 ASGI/SQLite 旅程均通过；后端反馈/历史专项86通过；H5编译与109项静态文件校验通过。历史全量前端曾因反馈页 SHA 未获批准而失败，Owner 随后批准确切新 SHA 并补充独立批准记录，素材保护专项已通过。后续全量结果和 Hosted CI 以最终提交实际运行记录为准。设备和实际播放均 NOT RUN。

恢复本轮的 guarded 全前端回归 723 passed、0 failed、0 skipped；其运行期间仅新增一项同事件并发与不同身份隔离测试，该文件在后续独立固定清单回归中 7 passed。原 720/1 的反馈页 SHA 失败已经由 Owner 的精确批准与源码保护检查真实解决，未跳过断言。
