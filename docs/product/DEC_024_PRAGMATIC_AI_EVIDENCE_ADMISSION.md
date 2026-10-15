## DEC-024: Pragmatic AI Evidence Admission 与一次摘要确认

- Status: Owner approved / downstream compatibility implemented, offline gates verified; awaiting Owner review. 不表示 Android Owner Gate 或 Sprint 6 验收通过。
- Decision: 用户一次确认事件的 scope 是 summary；系统按务实型 AI 证据合同接纳结构化候选。confirmed 保持下游事实资格状态，不表示用户逐条核实。现有 UI 不增加核对区域、按钮或二次确认。
- Authority: DEC-002 保持。摘要省略不是否认；独立原始资料证据不能仅因省略而丢弃。明确且可判定的纠正、来源错误、时间错误和关键矛盾必须受到保护；不承诺任意医学自由文本的完全语义证明。
- Rejected: 拒绝在原 revision 内有效，历史不可变；新全文投影不开发跨版本 rejected identity matching。本决定取代 DEC-023 的跨版本自动拒绝继承要求；DEC-023 原文作为历史记录保留。
- Internal contract: UnderstandingRevision.presentation_json.evidence_admission 保存版本、summary checksum、确认事件、run/revision/input 绑定、实际 fact identity、来源/span/checksum、系统接纳依据、执行检查和未覆盖不确定性。不新增公共 Schema、数据库列或 migration，不通过公开 Understanding API 返回审计对象。
- Implementation: 已有一次请求内 reconciliation、接纳审计和 revision/CAS 事务提交；Provider、接纳或 CAS 失败不发布新 confirmed revision。日期角色校验排除打印/导出/出生日期，多次就诊日期歧义保守处理。Mock 使用受控候选并遵循成功/失败及 revision 状态合同，不证明真实 AI 准确性。
- Downstream closure: diagnosis_service._edited_summary_override 对新版 pragmatic_ai_evidence_v1 增加严格 opt-in 验证：当前 run/revision/input 与活动资料、摘要及来源 checksum、成功确认事件、具体 fact identity、来源/span、confirmed/disposition 和实际执行的检查必须一致。复用已批准的确定性接纳检查，不新增医学推断。任何候选不合格时保守 suppress 整组 projection，避免复用含不合格证据的 organ 聚合；后续 Assessment revision 不得绕过验证。无新版审计的 legacy 保护不变，不改写旧记录或公开摘要。
- Validation: 原始 document 与 user_correction 混合来源经真实确认、Assessment 和 Diagnosis Router 的隔离测试成功消费；用户摘要保持原文，历史证据仍为 source_recorded。尚不证明任意自由文本语义准确性；确认事件记录或必要来源被移除时保守不放行，不以缺失审计扩大证据权限。
- Safety: 不调整 Two-Mode、dominance、organ mapping、RAG、Provider、Prompt Compiler、GenerationSpec、MusicAsset、Player 或已完成 Explanation Quality 规则。
