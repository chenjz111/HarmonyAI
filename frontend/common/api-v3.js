/**
 * HarmonyAI V3 前端客户端（v3-owner-flow-1）
 *
 * 合同依据：
 *  - docs/contracts/harmonyai-v3-owner-flow-amendment-001.md（Owner 修正案，权威）
 *  - docs/contracts/frontend-read-model-contract-v3.md（前端 Read Model）
 *
 * 设计原则：
 *  1. 页面只渲染后端返回的 Read Model，不在前端构造后端对象
 *  2. 不向用户展示 Provider、raw confidence、内部 enum、内部任务 ID
 *  3. 后端失败走友好降级文案，不白屏
 *  4. mock 数据全部为虚构脱敏内容，不含任何真实用户信息
 *
 * 说明：后端 /api/v3 尚未部署（依赖 Issue #79 / #78），
 * 当前 USE_MOCK 默认开启，按 Read Model 形状返回 fixture，
 * 联调时切换 USE_MOCK=false 即走真实接口。
 */

// ===== 配置 =====

const USE_MOCK = true // 联调时改为 false；勿在真实联调分支提交 true

const BASE_URL = "http://localhost:8000"

function authHeaders() {
  const token = uni.getStorageSync("v3_access_token") || ""
  return token ? { Authorization: "Bearer " + token } : {}
}

function idempotencyKey() {
  return "idem-" + Date.now() + "-" + Math.random().toString(36).slice(2, 10)
}

// ===== 真实请求（联调用） =====

function realRequest(path, { method = "GET", data = null, headers = {} } = {}) {
  return new Promise((resolve, reject) => {
    uni.request({
      url: BASE_URL + path,
      method,
      data: data || undefined,
      header: Object.assign({ "Content-Type": "application/json" }, authHeaders(), headers),
      success(res) {
        // Read Model envelope: { data, error }
        const body = res.data || {}
        if (res.statusCode >= 200 && res.statusCode < 300 && body.data !== undefined) {
          resolve(body.data)
        } else {
          const err = body.error || {}
          reject(Object.assign(new Error(err.message || "请求失败"), {
            code: err.code || "REQUEST_FAILED",
            status: res.statusCode,
          }))
        }
      },
      fail() {
        reject(Object.assign(new Error("网络连接失败，请稍后重试"), { code: "NETWORK_ERROR" }))
      },
    })
  })
}

// ===== Mock 状态机 =====
// 虚构 fixture：模拟一个完整 V3 会话的生命周期。
// 所有内容均为脱敏虚构，不对应任何真实用户。

const MOCK = {
  token: null,
  session: null, // { session_id, flow_contract_version, input_mode, input_revision, active_document_id, understanding_ref, questionnaire_ref }
  document: null, // { document_id, state, uploaded_at }
  understanding: null, // Read Model §4 case_summary
  transcript: null,
  questionnaireSubmission: null,
  assessment: null, // Read Model §8 assessment_confirmation
  basis: null, // Read Model §10 music_basis
  musicTask: null, // Read Model §11
  music: null, // Read Model §12 player
  feedbackDone: false,
}

function clone(obj) {
  return JSON.parse(JSON.stringify(obj))
}

// ---- mock: 问卷 schema（Read Model §6，10题，审核状态 approved）----
// 注：题目文案为占位示例，生产必须以医学审核 manifest 为准（checksum 校验）
const MOCK_QUESTIONNAIRE_SCHEMA = {
  page: "questionnaire_v3",
  schema_id: "questionnaire_v3",
  schema_version: "3.0.0",
  manifest_version: "medical_v3.0",
  content_checksum: "sha256:mock-fixture-checksum",
  time_window: "past_7_days",
  review_status: "approved",
  time_window_days: 7,
  title: "五脏状态问卷",
  question_count: 10,
  required_for_flow: false, // 由 session 权威模式决定（无资料=true）
  skip_action: { id: "skip_questionnaire", label: "跳过问卷，继续评估", style: "link", enabled: true },
  estimated_minutes: 3,
  questions: buildMockQuestions(),
}

function buildMockQuestions() {
  // 10 道五脏状态题（肝/心/脾/肺/肾 各2题），multi_choice_evidence
  const defs = [
    { id: "q01", organ: "肝", prompt: "最近 7 天，你是否有过以下胁肋或情绪方面的感受？", options: [["flank_discomfort", "胁肋部不适"], ["irritability", "容易急躁"], ["sighing", "常叹气"], ["eye_dryness", "眼睛干涩"]] },
    { id: "q02", organ: "肝", prompt: "最近 7 天，睡眠中是否出现多梦或易醒？", options: [["dream_disturbed_sleep", "多梦"], ["early_waking", "易醒难再入睡"], ["difficulty_falling_asleep", "入睡困难"]] },
    { id: "q03", organ: "心", prompt: "最近 7 天，是否有过心慌、心悸或胸前不适？", options: [["palpitations", "心慌心悸"], ["chest_tightness", "胸前闷"], ["insomnia_with_anxiety", "心烦难以入睡"]] },
    { id: "q04", organ: "心", prompt: "最近 7 天，白天精神状态如何？", options: [["daytime_fatigue", "白天精神不足"], ["poor_concentration", "注意力难集中"], ["low_mood", "情绪低落"]] },
    { id: "q05", organ: "脾", prompt: "最近 7 天，食欲和消化情况如何？", options: [["poor_appetite", "食欲不振"], ["bloating", "饭后腹胀"], ["loose_stool", "大便偏稀"]] },
    { id: "q06", organ: "脾", prompt: "最近 7 天，是否感觉身体沉重或倦怠乏力？", options: [["heaviness", "身体沉重"], ["fatigue_after_meals", "饭后困倦"], ["limb_weakness", "四肢无力"]] },
    { id: "q07", organ: "肺", prompt: "最近 7 天，呼吸或咽喉是否有以下情况？", options: [["short_breath", "气短"], ["dry_cough", "干咳少痰"], ["throat_dryness", "咽喉干燥"]] },
    { id: "q08", organ: "肺", prompt: "最近 7 天，是否容易出汗（静息时也出汗）？", options: [["spontaneous_sweating", "白天稍动就出汗"], ["night_sweats", "睡着后出汗"]] },
    { id: "q09", organ: "肾", prompt: "最近 7 天，腰部或膝盖是否有酸软感？", options: [["sore_lower_back", "腰酸"], ["weak_knees", "膝软"], ["heel_pain", "足跟不适"]] },
    { id: "q10", organ: "肾", prompt: "最近 7 天，是否怕冷或手脚发凉？", options: [["cold_limbs", "手脚发凉"], ["aversion_to_cold", "比一般人怕冷"], ["nighttime_frequent_urination", "夜尿偏多"]] },
  ]
  return defs.map((d, idx) => ({
    question_id: d.id,
    position: idx + 1,
    prompt: d.prompt,
    answer_type: "multi_choice_evidence",
    required: true,
    min_selections: 1,
    max_selections: 5,
    options: d.options.map(([code, label]) => ({
      option_code: code,
      label: label,
      claim_code: code,
      is_none: false,
      exclusive_with: [],
    })).concat([{
      option_code: "none",
      label: "无以上情况",
      claim_code: null,
      is_none: true,
      exclusive_with: ["*"],
    }]),
  }))
}

// ---- mock: 资料摘要（Read Model §4，虚构脱敏内容） ----
function mockCaseSummary() {
  return {
    page: "case_summary",
    understanding_id: "und_mock_001",
    revision: 1,
    status: "needs_confirmation",
    title: "请确认资料摘要",
    summary: "资料中提到近期入睡偏慢、睡眠恢复不足，白天精神状态一般，其他方面未见明显异常描述。",
    editable_fields: [
      {
        target_id: "fact_sleep_mock_001",
        label: "睡眠情况",
        value: { type: "text", value: "近期入睡偏慢、睡眠恢复不足" },
        max_length: 300,
        required: false,
      },
      {
        target_id: "fact_energy_mock_001",
        label: "白天状态",
        value: { type: "text", value: "白天精神状态一般" },
        max_length: 300,
        required: false,
      },
    ],
    source_notice: "以下内容是系统根据你上传的资料整理出的简要信息。请确认它是否准确反映你的近期情况。",
    warnings: [],
    actions: [
      { id: "confirm", label: "内容基本准确，继续", style: "primary", enabled: true, endpoint: "/api/v3/understandings/und_mock_001/confirmations", method: "POST" },
      { id: "edit", label: "修改资料摘要", style: "secondary", enabled: true },
      { id: "reupload", label: "重新上传资料", style: "secondary", enabled: true },
      { id: "discard_document", label: "改用描述与问卷", style: "link", enabled: true, endpoint: "/api/v3/sessions/sess_mock_001/input-transitions", method: "POST" },
    ],
  }
}

// ---- mock: 最终评估确认（Read Model §8） ----
function mockAssessment() {
  return {
    page: "assessment_confirmation",
    assessment_id: "asmt_mock_001",
    revision: 1,
    status: "needs_confirmation",
    safety_policy: "deferred_v3", // NOT_USER_VISIBLE
    safety_evaluation_status: "not_run", // NOT_USER_VISIBLE
    safety_status: null, // NOT_USER_VISIBLE
    title: "确认一下我们对你当前状态的理解",
    summary: "近期主要表现为思虑偏多、睡眠恢复不足和白天精力下降。",
    sections: [
      { id: "body", title: "身体感受", items: ["睡眠恢复不足", "白天精力下降"] },
      { id: "context", title: "最近情况", items: ["近期学习/工作安排带来一定压力"] },
    ],
    editable_items: [
      {
        target_id: "fev_mock_sleep",
        label: "睡眠恢复不足",
        value: { type: "severity", value: "moderate" },
        allowed_values: ["none", "mild", "moderate", "severe"],
        required: false,
      },
      {
        target_id: "fev_mock_energy",
        label: "白天精力下降",
        value: { type: "severity", value: "mild" },
        allowed_values: ["none", "mild", "moderate", "severe"],
        required: false,
      },
    ],
    degradation_notice: null,
    actions: [
      { id: "confirm", label: "基本符合，继续", style: "primary", enabled: true, endpoint: "/api/v3/assessments/asmt_mock_001/confirmations", method: "POST" },
      { id: "correct", label: "有些地方不对，我要修改", style: "secondary", enabled: true },
    ],
  }
}

// ---- mock: 音乐生成依据（Read Model §10） ----
function mockBasis() {
  return {
    page: "music_basis",
    diagnosis_id: "diag_mock_001",
    prescription_id: "rx_mock_001",
    title: "本次音乐生成依据",
    tendency: { label: "心脾两虚倾向", disclaimer: "仅用于音乐调养参考，不构成医学诊断。" },
    basis_summaries: ["思虑偏多", "睡眠恢复不足", "精力下降"],
    tone_profile: { dominant_tone: "gong", dominant_label: "宫音", summary: "本次以宫音为主。" },
    music_parameters: {
      bpm: 58,
      duration_seconds: 300,
      instrument_labels: ["古琴", "洞箫"],
      ambient_labels: ["流水"],
    },
    personalization_summary: "已参考你过去的音乐偏好。",
    actions: [{ id: "generate", label: "生成本次音乐", style: "primary", enabled: true }],
  }
}

// ---- mock: 播放器（Read Model §12） ----
function mockMusic(sourceType) {
  return {
    page: "player",
    music_ref: { music_id: "asset_mock_001", source_type: sourceType || "generated" },
    title: "宫调·静心",
    stream_url: "/static/music/jiao-demo.wav", // mock：使用本地示例音频（仅测试）
    duration_seconds: 300,
    source_label: (sourceType === "matched_fallback") ? "审核曲库匹配音乐" : "AI生成音乐",
    tone_label: "宫音为主",
    instrument_labels: ["古琴", "洞箫"],
    controls: { play: true, pause: true, seek: true, favorite: true },
    favorite: false,
    disclaimer: "音乐调养不能替代专业医疗或心理帮助。",
  }
}

function delay(ms) {
  return new Promise((r) => setTimeout(r, ms))
}

// ===== Mock Handler =====
// 按 Owner Amendment 流程实现完整状态机；页面通过这些函数驱动 UI。

const mockApi = {
  // POST /api/v3/auth/guest
  async guestAuth() {
    await delay(200)
    MOCK.token = {
      access_token: "mock-token-" + Math.random().toString(36).slice(2),
      token_type: "Bearer",
      expires_at: new Date(Date.now() + 86400000).toISOString(),
      public_user_id: "u_guest_mock",
    }
    try { uni.setStorageSync("v3_access_token", MOCK.token.access_token) } catch (e) { /* H5/小程序差异忽略 */ }
    return clone(MOCK.token)
  },

  // POST /api/v3/sessions { flow_contract_version }
  async createSession() {
    await delay(300)
    MOCK.session = {
      session_id: "sess_mock_001",
      flow_contract_version: "v3-owner-flow-1",
      input_mode: null,
      input_revision: 1,
      active_document_id: null,
      understanding_ref: null,
      questionnaire_ref: null,
    }
    MOCK.document = null
    MOCK.understanding = null
    MOCK.questionnaireSubmission = null
    MOCK.assessment = null
    MOCK.basis = null
    MOCK.musicTask = null
    MOCK.music = null
    MOCK.feedbackDone = false
    return clone(MOCK.session)
  },

  getSession() {
    if (!MOCK.session) {
      return Promise.reject(Object.assign(new Error("会话未创建"), { code: "SESSION_NOT_FOUND" }))
    }
    return Promise.resolve(clone(MOCK.session))
  },

  // POST /api/v3/sessions/{id}/input-transitions
  // action: select_mode | replace_document | discard_document
  async inputTransition(action, payload = {}) {
    await delay(300)
    const s = MOCK.session
    if (!s) throw Object.assign(new Error("会话未创建"), { code: "SESSION_NOT_FOUND" })
    if (action === "select_mode") {
      if (s.input_mode !== null) {
        throw Object.assign(new Error("入口已选择，不能重复选择"), { code: "INPUT_REVISION_CONFLICT", status: 409 })
      }
      s.input_mode = payload.input_mode
      return clone(s)
    }
    if (action === "replace_document") {
      if (!payload.document_id) {
        throw Object.assign(new Error("缺少新资料标识"), { code: "VALIDATION_ERROR", status: 422 })
      }
      s.input_mode = "with_document"
      s.input_revision += 1
      s.active_document_id = payload.document_id
      s.understanding_ref = null // 旧摘要失效（Amendment §3.4）
      MOCK.understanding = null
      return clone(s)
    }
    if (action === "discard_document") {
      s.input_mode = "without_document"
      s.input_revision += 1
      s.active_document_id = null
      s.understanding_ref = null
      MOCK.understanding = null
      MOCK.document = null
      return clone(s)
    }
    throw Object.assign(new Error("未知操作"), { code: "VALIDATION_ERROR", status: 422 })
  },

  // POST /api/v3/documents（上传）
  // mock 行为：文件名带 "fail" 时模拟 OCR 失败，否则处理成功
  async uploadDocument(fileName) {
    await delay(1200) // 模拟 OCR 处理
    const fail = fileName && String(fileName).toLowerCase().indexOf("fail") !== -1
    MOCK.document = {
      document_id: "doc_mock_" + Date.now(),
      state: fail ? "failed" : "ready",
      uploaded_at: new Date().toISOString(),
    }
    const s = MOCK.session
    if (s && fail) {
      // 失败资源保留 ID 供重试，但不是有效来源（Amendment §4.1）
      s.active_document_id = MOCK.document.document_id
    } else if (s) {
      s.active_document_id = MOCK.document.document_id
    }
    return clone(MOCK.document)
  },

  // 资料来源状态（Read Model §3.2 SourceStatusReadModel）
  getSourceStatus() {
    if (!MOCK.document) {
      return Promise.reject(Object.assign(new Error("尚无上传资料"), { code: "NOT_FOUND", status: 404 }))
    }
    const d = MOCK.document
    const stateLabel = {
      processing: "正在识别资料",
      ready: "资料识别完成",
      failed: "资料暂未识别成功",
    }
    return Promise.resolve(clone({
      source_id: d.document_id,
      source_type: "document",
      state: d.state,
      label: stateLabel[d.state] || "正在识别资料",
      message: d.state === "failed"
        ? "我们暂时无法从这份资料中提取有效内容。你可以重新上传清晰的图片或PDF，也可以跳过本次资料，改用最近情况描述和10道状态问卷继续评估。"
        : "通常需要几秒钟。",
      can_skip: false,
      actions: [
        { id: "discard_document", label: "改用描述与问卷", style: "secondary", enabled: true, endpoint: "/api/v3/sessions/sess_mock_001/input-transitions", method: "POST" },
      ],
    }))
  },

  // GET understanding（摘要确认页数据）
  // 仅当 OCR 成功后可获取；失败/处理中不可进入摘要确认（Amendment §3.1）
  getCaseSummary() {
    if (!MOCK.document || MOCK.document.state !== "ready") {
      return Promise.reject(Object.assign(
        new Error("资料尚未识别成功，不能进入摘要确认"),
        { code: "SOURCE_NOT_READY", status: 409 },
      ))
    }
    if (!MOCK.understanding) {
      MOCK.understanding = mockCaseSummary()
      MOCK.session.understanding_ref = { understanding_id: "und_mock_001", revision: 1 }
    }
    return Promise.resolve(clone(MOCK.understanding))
  },

  // POST /api/v3/understandings/{id}/confirmations
  // decision: confirm | confirm_with_changes
  async confirmUnderstanding(payload) {
    await delay(500)
    const u = MOCK.understanding
    if (!u) {
      throw Object.assign(new Error("摘要不存在"), { code: "NOT_FOUND", status: 404 })
    }
    if (payload.expected_revision !== u.revision) {
      throw Object.assign(new Error("摘要已被更新，请刷新后重试"), { code: "REVISION_CONFLICT", status: 409 })
    }
    if (payload.decision === "confirm") {
      u.status = "confirmed"
      u.revision += 1
      MOCK.session.understanding_ref = { understanding_id: u.understanding_id, revision: u.revision }
      return clone(u)
    }
    if (payload.decision === "confirm_with_changes") {
      // 全文修改：edited_summary_text + reprocess_requested=true（Amendment §4.2）
      const text = (payload.edited_summary_text || "").trim()
      if (!text || text.length > 2000) {
        throw Object.assign(new Error("摘要文本需要 1-2000 字"), { code: "VALIDATION_ERROR", status: 422 })
      }
      u.summary = text
      u.revision += 1
      u.status = "confirmed"
      MOCK.session.understanding_ref = { understanding_id: u.understanding_id, revision: u.revision }
      return clone(u)
    }
    throw Object.assign(new Error("未知确认类型"), { code: "VALIDATION_ERROR", status: 422 })
  },

  // GET /api/v3/questionnaire/schema
  async getQuestionnaireSchema() {
    await delay(200)
    const schema = clone(MOCK_QUESTIONNAIRE_SCHEMA)
    // 由 session 权威模式决定必填性（Read Model §6）
    if (MOCK.session && MOCK.session.input_mode === "without_document") {
      schema.required_for_flow = true
      schema.skip_action = null
    }
    return schema
  },

  // POST /api/v3/questionnaire/submissions
  async submitQuestionnaire(answers) {
    await delay(600)
    const schema = MOCK_QUESTIONNAIRE_SCHEMA
    // 校验 10 题完整（无资料模式必须完整提交）
    const missing = schema.questions.filter((q) => !answers[q.question_id] || !answers[q.question_id].length)
    if (missing.length) {
      throw Object.assign(new Error("还有 " + missing.length + " 题未作答"), { code: "QUESTIONNAIRE_INCOMPLETE", status: 422 })
    }
    MOCK.questionnaireSubmission = {
      questionnaire_submission_id: "qsub_mock_" + Date.now(),
      schema_id: schema.schema_id,
      schema_version: schema.schema_version,
      manifest_version: schema.manifest_version,
      content_checksum: schema.content_checksum,
      submitted_at: new Date().toISOString(),
      answers: clone(answers),
    }
    MOCK.session.questionnaire_ref = {
      questionnaire_submission_id: MOCK.questionnaireSubmission.questionnaire_submission_id,
      schema_id: schema.schema_id,
      schema_version: schema.schema_version,
      manifest_version: schema.manifest_version,
      content_checksum: schema.content_checksum,
    }
    return clone(MOCK.questionnaireSubmission)
  },

  // POST /api/v3/assessments（触发 Agent1 评估）
  async createAssessment() {
    await delay(1500) // 模拟 Agent1 分析
    const s = MOCK.session
    // 无资料模式必须先有完整问卷（Amendment §4.3）
    if (s.input_mode === "without_document" && !MOCK.questionnaireSubmission) {
      throw Object.assign(new Error("请先完成 10 道状态问卷"), { code: "QUESTIONNAIRE_REQUIRED", status: 422 })
    }
    MOCK.assessment = mockAssessment()
    return clone(MOCK.assessment)
  },

  getAssessment() {
    if (!MOCK.assessment) {
      return Promise.reject(Object.assign(new Error("评估尚未生成"), { code: "NOT_FOUND", status: 404 }))
    }
    return Promise.resolve(clone(MOCK.assessment))
  },

  // POST /api/v3/assessments/{id}/confirmations（唯一最终确认）
  async confirmAssessment(payload) {
    await delay(500)
    const a = MOCK.assessment
    if (!a) {
      throw Object.assign(new Error("评估不存在"), { code: "NOT_FOUND", status: 404 })
    }
    if (payload.expected_revision !== a.revision) {
      throw Object.assign(new Error("评估已被更新，请刷新后重试"), { code: "REVISION_CONFLICT", status: 409 })
    }
    // 修正提交：带 changes[]，返回 revision+1 的完整 Read Model
    if (payload.decision === "confirm_with_changes" && Array.isArray(payload.changes)) {
      payload.changes.forEach((c) => {
        const item = a.editable_items.find((i) => i.target_id === c.target_id)
        if (item && item.value.type === "severity") {
          item.value.value = c.new_value
        }
      })
      a.summary = a.sections.flatMap((sec) => sec.items).slice(0, 3).join("、")
    }
    a.revision += 1
    a.status = "confirmed"
    return clone(a)
  },

  // 评估确认后 → 音乐生成依据（Agent2/3 结果）
  async getMusicBasis() {
    await delay(800)
    if (!MOCK.assessment || MOCK.assessment.status !== "confirmed") {
      throw Object.assign(new Error("请先完成最终确认"), { code: "ASSESSMENT_NOT_CONFIRMED", status: 409 })
    }
    MOCK.basis = mockBasis()
    return clone(MOCK.basis)
  },

  // POST /api/v3/music/tasks（发起生成）
  async startMusicGeneration() {
    await delay(300)
    MOCK.musicTask = {
      page: "music_generation",
      task_id: "task_mock_" + Date.now(),
      status: "queued",
      title: "正在生成音乐",
      progress: { value: 0, indeterminate: true }, // Provider 未报告真实进度时不伪造百分比
      message: "正在根据本次音乐参数生成。",
      poll_after_ms: 1200,
      can_cancel: true,
      actions: [{ id: "cancel", label: "取消生成", style: "secondary", enabled: true }],
      _elapsed: 0,
    }
    return clone(stripInternal(MOCK.musicTask))
  },

  // GET /api/v3/music/tasks/{id}（轮询）
  async pollMusicGeneration() {
    await delay(400)
    const t = MOCK.musicTask
    if (!t) {
      throw Object.assign(new Error("生成任务不存在"), { code: "NOT_FOUND", status: 404 })
    }
    t._elapsed = (t._elapsed || 0) + 1
    if (t.status === "cancelled") return clone(stripInternal(t))
    if (t._elapsed <= 1) {
      t.status = "running"
      t.progress = { value: 0, indeterminate: true }
    } else if (t._elapsed <= 3) {
      t.status = "running"
      t.progress = { value: Math.min(t._elapsed * 30, 90), indeterminate: false }
    } else {
      t.status = "succeeded"
      t.progress = { value: 100, indeterminate: false }
      MOCK.music = mockMusic("generated")
    }
    return clone(stripInternal(t))
  },

  async cancelMusicGeneration() {
    await delay(200)
    if (MOCK.musicTask) {
      MOCK.musicTask.status = "cancelled"
      return clone(stripInternal(MOCK.musicTask))
    }
    throw Object.assign(new Error("生成任务不存在"), { code: "NOT_FOUND", status: 404 })
  },

  // 获取播放数据（Read Model §12）
  getMusic() {
    if (!MOCK.music) {
      return Promise.reject(Object.assign(new Error("音乐尚未生成完成"), { code: "NOT_FOUND", status: 404 }))
    }
    return Promise.resolve(clone(MOCK.music))
  },

  // POST /api/v3/feedback（Read Model §13）
  async submitFeedback(payload) {
    await delay(400)
    MOCK.feedbackDone = true
    return { received: true }
  },
}

function stripInternal(obj) {
  const out = clone(obj)
  Object.keys(out).forEach((k) => {
    if (k.indexOf("_") === 0) delete out[k]
  })
  return out
}

// ===== 对外接口 =====

export const apiV3 = {
  USE_MOCK,

  guestAuth() {
    return USE_MOCK ? mockApi.guestAuth() : realRequest("/api/v3/auth/guest", { method: "POST" })
  },
  createSession() {
    return USE_MOCK
      ? mockApi.createSession()
      : realRequest("/api/v3/sessions", { method: "POST", data: { flow_contract_version: "v3-owner-flow-1" } })
  },
  getSession() {
    return USE_MOCK ? mockApi.getSession() : realRequest("/api/v3/sessions/current")
  },
  selectMode(inputMode) {
    return USE_MOCK
      ? mockApi.inputTransition("select_mode", { input_mode: inputMode })
      : realRequest("/api/v3/sessions/current/input-transitions", {
          method: "POST",
          data: { action: "select_mode", input_mode: inputMode, expected_input_revision: 1 },
          headers: { "Idempotency-Key": idempotencyKey() },
        })
  },
  replaceDocument(documentId, expectedInputRevision) {
    return USE_MOCK
      ? mockApi.inputTransition("replace_document", { document_id: documentId })
      : realRequest("/api/v3/sessions/current/input-transitions", {
          method: "POST",
          data: { action: "replace_document", document_id: documentId, expected_input_revision: expectedInputRevision },
          headers: { "Idempotency-Key": idempotencyKey() },
        })
  },
  discardDocument(expectedInputRevision) {
    return USE_MOCK
      ? mockApi.inputTransition("discard_document", { expected_input_revision: expectedInputRevision })
      : realRequest("/api/v3/sessions/current/input-transitions", {
          method: "POST",
          data: { action: "discard_document", expected_input_revision: expectedInputRevision },
          headers: { "Idempotency-Key": idempotencyKey() },
        })
  },
  uploadDocument(filePath, fileName) {
    if (USE_MOCK) return mockApi.uploadDocument(fileName)
    return new Promise((resolve, reject) => {
      uni.uploadFile({
        url: BASE_URL + "/api/v3/documents",
        filePath,
        name: "file",
        header: authHeaders(),
        success(res) {
          try {
            const body = JSON.parse(res.data)
            if (res.statusCode >= 200 && res.statusCode < 300) resolve(body.data)
            else reject(Object.assign(new Error((body.error && body.error.message) || "上传失败"), { code: (body.error && body.error.code) || "UPLOAD_FAILED" }))
          } catch (e) {
            reject(Object.assign(new Error("上传响应异常"), { code: "UPLOAD_FAILED" }))
          }
        },
        fail() {
          reject(Object.assign(new Error("网络连接失败，请稍后重试"), { code: "NETWORK_ERROR" }))
        },
      })
    })
  },
  getSourceStatus() {
    return USE_MOCK ? mockApi.getSourceStatus() : realRequest("/api/v3/documents/current")
  },
  getCaseSummary() {
    return USE_MOCK ? mockApi.getCaseSummary() : realRequest("/api/v3/understandings/current")
  },
  confirmUnderstanding(payload) {
    return USE_MOCK
      ? mockApi.confirmUnderstanding(payload)
      : realRequest("/api/v3/understandings/current/confirmations", {
          method: "POST",
          data: Object.assign({ schema_version: "understanding_v3.1" }, payload),
          headers: { "Idempotency-Key": idempotencyKey() },
        })
  },
  getQuestionnaireSchema() {
    return USE_MOCK ? mockApi.getQuestionnaireSchema() : realRequest("/api/v3/questionnaire/schema")
  },
  submitQuestionnaire(answers) {
    return USE_MOCK
      ? mockApi.submitQuestionnaire(answers)
      : realRequest("/api/v3/questionnaire/submissions", {
          method: "POST",
          data: {
            schema_version: "assessment_v3.1",
            session_id: uni.getStorageSync("v3_session_id") || undefined,
            answers,
          },
          headers: { "Idempotency-Key": idempotencyKey() },
        })
  },
  createAssessment(expectedInputRevision) {
    return USE_MOCK
      ? mockApi.createAssessment()
      : realRequest("/api/v3/assessments", {
          method: "POST",
          data: {
            schema_version: "assessment_v3.1",
            session_id: uni.getStorageSync("v3_session_id") || undefined,
            expected_input_revision: expectedInputRevision,
          },
          headers: { "Idempotency-Key": idempotencyKey() },
        })
  },
  getAssessment() {
    return USE_MOCK ? mockApi.getAssessment() : realRequest("/api/v3/assessments/current")
  },
  confirmAssessment(payload) {
    return USE_MOCK
      ? mockApi.confirmAssessment(payload)
      : realRequest("/api/v3/assessments/current/confirmations", {
          method: "POST",
          data: Object.assign({ schema_version: "assessment_v3.1" }, payload),
          headers: { "Idempotency-Key": idempotencyKey() },
        })
  },
  getMusicBasis() {
    return USE_MOCK ? mockApi.getMusicBasis() : realRequest("/api/v3/diagnosis/current/basis")
  },
  startMusicGeneration() {
    return USE_MOCK
      ? mockApi.startMusicGeneration()
      : realRequest("/api/v3/music/tasks", { method: "POST", headers: { "Idempotency-Key": idempotencyKey() } })
  },
  pollMusicGeneration() {
    return USE_MOCK ? mockApi.pollMusicGeneration() : realRequest("/api/v3/music/tasks/current")
  },
  cancelMusicGeneration() {
    return USE_MOCK ? mockApi.cancelMusicGeneration() : realRequest("/api/v3/music/tasks/current", { method: "DELETE" })
  },
  getMusic() {
    return USE_MOCK ? mockApi.getMusic() : realRequest("/api/v3/music/current")
  },
  submitFeedback(payload) {
    return USE_MOCK
      ? mockApi.submitFeedback(payload)
      : realRequest("/api/v3/feedback", { method: "POST", data: payload, headers: { "Idempotency-Key": idempotencyKey() } })
  },

  // 会话辅助：页面间共享 mock session id（真实模式由服务端返回）
  rememberSession(session) {
    if (session && session.session_id) {
      try { uni.setStorageSync("v3_session_id", session.session_id) } catch (e) { /* ignore */ }
    }
  },
}

export default apiV3
