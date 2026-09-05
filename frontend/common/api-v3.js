/**
 * HarmonyAI V3 前端客户端（v3-owner-flow-1）
 *
 * 合同依据：
 *  - docs/contracts/harmonyai-v3-owner-flow-amendment-001.md（Owner 修正案，权威）
 *  - docs/contracts/frontend-read-model-contract-v3.md（前端 Read Model）
 *  - 后端已交付接口：
 *      POST /api/v3/auth/guest
 *      POST /api/v3/sessions                          {flow_contract_version}
 *      GET  /api/v3/sessions/{session_id}
 *      POST /api/v3/sessions/{session_id}/input-transitions   (select_mode/replace_document/discard_document)
 *      POST /api/v3/understandings                    (multi-source ingestion，narrative 源支持 inline text)
 *      GET  /api/v3/understandings/{understanding_id}
 *      POST /api/v3/understandings/{understanding_id}/confirmations
 *      POST /api/v3/music/generations                 (依赖辨证处方能力，见下方已知后端缺口)
 *      GET  /api/v3/music/generations/{task_id}
 *      POST /api/v3/music/generations/{task_id}/cancel
 *      GET  /api/v3/music/assets/{music_id}/stream
 *      POST /api/v3/feedback
 *      GET/PUT/DELETE /api/v3/favorites…, GET /api/v3/me/history, GET /api/v3/me/preferences
 *    文件上传复用 V2：POST /api/v2/documents（multipart，归属限制见下方已知后端缺口）
 *
 * 设计原则：
 *  1. 页面只渲染后端返回的 Read Model，不在前端构造后端对象
 *  2. 不向用户展示 Provider、raw confidence、内部 enum、内部任务 ID
 *  3. 后端失败走友好降级文案，不白屏；绝不把 mock 数据伪装成真实 AI 结果
 *  4. mock 数据全部为虚构脱敏内容，不含任何真实用户信息
 *
 * 模式（mock 只能显式开启，默认 real）：
 *  - "real"（默认）：全部走真实后端。后端尚未交付的智能化能力
 *    （问卷提交→综合评估、辨证、音乐生成）返回 AGENT_PENDING 错误，
 *    页面显示明确的"服务升级维护中"等待状态，绝不伪造成功。
 *  - "hybrid"（显式）：输入段（鉴权/会话/输入切换/资料上传/资料理解）走真实后端，
 *    Agent 段（评估/辨证/生成）走 mock 演示数据，页面显示"演示数据"标识。
 *  - "mock"（显式）：全 fixture 状态机，供自动测试与本地开发。
 *  开启方式（仅显式 —— 默认 real）：
 *  - 构建环境变量 VITE_HARMONYAI_V3_MODE=mock|hybrid|real（Vite import.meta.env，
 *    兼容旧名 HARMONYAI_V3_MODE）
 *  - Node 测试进程环境变量 process.env.HARMONYAI_V3_MODE
 *  - H5 本机视觉演示：localhost/127.0.0.1 + URL query ?harmonyai_demo=1
 *
 *  关键约束（P1-2 严格隔离）：
 *  - 正式运行（任意非 localhost 域名）默认 real，**不读** localStorage.Mock 配置，
 *    防止陈旧调试缓存污染正式会话。
 *  - mock/hybrid 仅由上述三种显式入口触发，未命中即返回 real。
 *
 * 已知后端缺口（如实上报，不静默绕过）：
 *  - V2 上传接口 /api/v2/documents 固定把资料写入默认用户，而 V3 访客是独立用户，
 *    replace_document/understanding 的归属校验会失败（DOCUMENT_NOT_FOUND）。
 *    有资料流程真实联调需要后端提供与会话绑定的上传端点（owner-aware upload）。
 *  - 问卷提交端点（POST /api/v3/questionnaire/submissions）与 V3 评估创建端点尚未交付。
 *  - 音乐生成依赖辨证处方标识，该能力尚未交付。
 *  - 有资料流程"已确认摘要 + 追加最近情况描述"需要后端支持向已确认
 *    Understanding 追加源；在此之前有资料路径的描述仅本机暂存（页面如实标注）。
 */

import { QUESTIONNAIRE_MANIFEST, FREQUENCY_OPTIONS } from "./questionnaire-v3-manifest.js"

// ===== 配置 =====

// 严格隔离：mock/hybrid 仅由显式入口触发；正式运行绝不读陈旧 localStorage 配置
function resolveMode() {
  // 1. 本机视觉演示（仅在显式 localhost + ?harmonyai_demo=1 时进入 mock）
  try {
    if (typeof location !== "undefined") {
      const host = location.hostname || ""
      const localHost = host === "127.0.0.1" || host === "localhost"
      const demo = new URLSearchParams(location.search || "").get("harmonyai_demo")
      if (localHost && demo === "1") return "mock"
    }
  } catch (e) { /* 非浏览器环境 */ }

  // 2. Vite 构建注入（兼容旧名 HARMONYAI_V3_MODE 与新名 VITE_HARMONYAI_V3_MODE）
  let mode = ""
  try {
    const env = (import.meta && import.meta.env) || {}
    mode = env.VITE_HARMONYAI_V3_MODE || env.HARMONYAI_V3_MODE || ""
  } catch (e) { /* 非 Vite 环境 */ }
  // 3. Node 测试进程
  if (!mode && typeof process !== "undefined" && process && process.env) {
    mode = process.env.HARMONYAI_V3_MODE || ""
  }
  if (mode === "mock" || mode === "hybrid" || mode === "real") return mode
  // 4. 默认 real —— 不允许陈旧 localStorage 配置污染正式域名（严格隔离）
  return "real"
}

const MODE = resolveMode()
// 输入段（鉴权/会话/资料/理解/最近情况描述）是否走真实后端
const INPUT_REAL = MODE !== "mock"
// 智能化能力段（评估/辨证/生成）是否暂用 mock 演示数据（仅 hybrid 显式开启）
const AGENT_MOCK = MODE !== "real"

const BASE_URL = (() => {
  try {
    return (import.meta.env && import.meta.env.VITE_API_BASE_URL) || "http://localhost:8000"
  } catch (e) {
    return "http://localhost:8000"
  }
})()

// ===== 安全存储（H5 用 uni storage，Node 测试降级内存 Map） =====

const memStore = {}

function safeGet(key) {
  try {
    const v = uni.getStorageSync(key)
    if (v !== "" && v !== undefined && v !== null) return v
  } catch (e) { /* uni 不可用（Node 测试） */ }
  return memStore[key]
}

function safeSet(key, value) {
  memStore[key] = value
  try { uni.setStorageSync(key, value) } catch (e) { /* ignore */ }
}

function safeRemove(key) {
  delete memStore[key]
  try { uni.removeStorageSync(key) } catch (e) { /* ignore */ }
}

// ===== 真实会话流转状态（跨页面共享；所有 revision 均来自后端响应） =====

const FLOW_STATE_KEY = "v3_flow_state"

function loadFlowState() {
  const raw = safeGet(FLOW_STATE_KEY)
  if (raw && typeof raw === "string") {
    try { return JSON.parse(raw) } catch (e) { return {} }
  }
  return raw && typeof raw === "object" ? raw : {}
}

function saveFlowState(patch) {
  const next = Object.assign(loadFlowState(), patch)
  safeSet(FLOW_STATE_KEY, JSON.stringify(next))
  return next
}

function clearFlowState() {
  safeRemove(FLOW_STATE_KEY)
}

function authHeaders() {
  const token = safeGet("v3_access_token") || ""
  return token ? { Authorization: "Bearer " + token } : {}
}

function idempotencyKey() {
  return "idem-" + Date.now() + "-" + Math.random().toString(36).slice(2, 10)
}

// ===== 友好错误映射（不暴露技术细节，但如实反映失败） =====

const FRIENDLY_ERRORS = {
  FACT_EXTRACTION_UNAVAILABLE: "当前暂不支持修改摘要后重新解析。你可以先按现有摘要继续，或重新上传资料。",
  INPUT_REVISION_CONFLICT: "输入状态已更新，请重新进入本页后再试。",
  REVISION_CONFLICT: "内容已更新，请刷新后重试。",
  DOCUMENT_NOT_FOUND: "上传的资料暂时无法关联到当前会话。你可以选择暂不使用这份资料，通过描述和问卷继续评估。",
  DOCUMENT_OCR_NOT_READY: "资料尚未成功识别，请重新上传，或改用最近情况描述和10道状态问卷继续评估。",
  UNAUTHENTICATED: "身份已失效，请重新进入体验。",
  NETWORK_ERROR: "网络连接失败，请检查网络后重试。",
}

function apiError(message, code, extra) {
  return Object.assign(new Error(message), Object.assign({ code: code || "REQUEST_FAILED" }, extra || {}))
}

// AGENT_PENDING：Agent 能力未接入时的统一等待状态（页面据此显示等待卡）
// P1-2：文案为稳定用户文案，不暴露 PR 编号等内部开发信息
function agentPendingError(what) {
  return apiError(
    what + "服务正在升级维护中，暂时无法使用。页面保持等待状态，不会影响你已填写的内容。",
    "AGENT_PENDING",
    { agentPending: true },
  )
}

// ===== 真实请求 =====

function realRequest(path, { method = "GET", data = null, headers = {} } = {}) {
  return new Promise((resolve, reject) => {
    try {
      uni.request({
        url: BASE_URL + path,
        method,
        data: data || undefined,
        header: Object.assign({ "Content-Type": "application/json" }, authHeaders(), headers),
        success(res) {
          // V3 envelope：成功 { ok:true, data, request_id, schema_version }
          //            失败 { ok:false, error:{ code, message, retryable, next_actions } }
          const body = res.data || {}
          if (res.statusCode >= 200 && res.statusCode < 300 && body.data !== undefined) {
            resolve(body.data)
          } else {
            const err = body.error || {}
            const friendly = FRIENDLY_ERRORS[err.code]
            reject(apiError(friendly || err.message || "请求失败", err.code || "REQUEST_FAILED", {
              status: res.statusCode,
              retryable: !!err.retryable,
              nextActions: err.next_actions || [],
            }))
          }
        },
        fail() {
          reject(apiError(FRIENDLY_ERRORS.NETWORK_ERROR, "NETWORK_ERROR"))
        },
      })
    } catch (e) {
      // uni 不可用（Node 测试环境）：按网络错误降级，不静默返回 mock 数据
      reject(apiError(FRIENDLY_ERRORS.NETWORK_ERROR, "NETWORK_ERROR"))
    }
  })
}

// V2 文件上传（multipart）。V2 envelope：{ success, data, error:{code,message}, meta }
function realUploadDocument(filePath, fileName) {
  return new Promise((resolve, reject) => {
    const state = loadFlowState()
    try {
      uni.uploadFile({
        url: BASE_URL + "/api/v2/documents",
        filePath,
        name: "file",
        formData: {
          session_id: state.session_id || "",
          document_type: "medical_record",
          consent_confirmed: "true",
        },
        header: authHeaders(),
        success(res) {
          let body = null
          try { body = JSON.parse(res.data) } catch (e) { /* ignore */ }
          if (res.statusCode >= 200 && res.statusCode < 300 && body && body.success) {
            resolve(body.data)
          } else {
            const err = (body && body.error) || {}
            reject(apiError(err.message || "上传失败，请重试", err.code || "UPLOAD_FAILED", {
              status: res.statusCode,
            }))
          }
        },
        fail() {
          reject(apiError(FRIENDLY_ERRORS.NETWORK_ERROR, "NETWORK_ERROR"))
        },
      })
    } catch (e) {
      // uni 不可用（Node 测试环境）：按网络错误降级
      reject(apiError(FRIENDLY_ERRORS.NETWORK_ERROR, "NETWORK_ERROR"))
    }
  })
}

// ===== 真实接口（输入段） =====

const realInputApi = {
  async guestAuth() {
    const data = await realRequest("/api/v3/auth/guest", { method: "POST" })
    safeSet("v3_access_token", data.access_token)
    safeSet("v3_public_user_id", data.public_user_id)
    return data
  },

  async createSession() {
    // 必须携带 flow_contract_version，否则后端创建的是 legacy 会话（无 input-transitions）
    const entry = await realRequest("/api/v3/sessions", {
      method: "POST",
      data: { flow_contract_version: "v3-owner-flow-1" },
      headers: { "Idempotency-Key": idempotencyKey() },
    })
    clearFlowState()
    saveFlowState({
      session_id: entry.session_id,
      input_revision: 1, // 后端契约：新流程会话 input_revision 从 1 开始
      input_mode: null,
      active_document_id: null,
    })
    return {
      session_id: entry.session_id,
      flow_contract_version: "v3-owner-flow-1",
      input_mode: null,
      input_revision: 1,
      active_document_id: null,
      understanding_ref: null,
      questionnaire_ref: null,
    }
  },

  async getSession() {
    const state = loadFlowState()
    if (!state.session_id) throw apiError("会话未创建", "SESSION_NOT_FOUND")
    const data = await realRequest("/api/v3/sessions/" + encodeURIComponent(state.session_id))
    saveFlowState({
      input_mode: data.input_mode,
      input_revision: data.input_revision,
      active_document_id: data.active_document_id,
    })
    return data
  },

  async inputTransition(action, payload = {}) {
    const state = loadFlowState()
    if (!state.session_id) throw apiError("会话未创建", "SESSION_NOT_FOUND")
    const data = await realRequest(
      "/api/v3/sessions/" + encodeURIComponent(state.session_id) + "/input-transitions",
      {
        method: "POST",
        data: Object.assign({
          action,
          expected_input_revision: state.input_revision || 1,
        }, payload),
        headers: { "Idempotency-Key": idempotencyKey() },
      },
    )
    // input_revision 一律以后端响应为准，前端不猜测
    const patch = {
      input_mode: data.input_mode,
      input_revision: data.input_revision,
      active_document_id: data.active_document_id,
      understanding_ref: data.understanding_ref || null,
      questionnaire_ref: data.questionnaire_ref || null,
    }
    if (action === "replace_document") {
      // 资料替换后旧摘要/理解失效（Amendment §3.4），本机提交状态一并重置
      patch.understanding_id = null
      patch.understanding_revision = null
      patch.understanding_status = null
      patch.narrative_submitted = false
      patch.narrative_text = ""
    }
    saveFlowState(patch)
    return data
  },

  async selectMode(inputMode) {
    return realInputApi.inputTransition("select_mode", { input_mode: inputMode })
  },

  async replaceDocument(documentId) {
    return realInputApi.inputTransition("replace_document", { document_id: documentId })
  },

  async discardDocument() {
    return realInputApi.inputTransition("discard_document")
  },

  // 上传 = V2 文件上传 + OCR；成功后必须经 replace_document 绑定为活跃资料
  async uploadDocument(filePath) {
    const up = await realUploadDocument(filePath)
    // ocr_status：confirmed | needs_confirmation → 可用；degraded | failed → OCR 失败分流
    const usable = up && (up.ocr_status === "confirmed" || up.ocr_status === "needs_confirmation")
    if (!usable) {
      return { document_id: up.document_id, state: "failed" }
    }
    await realInputApi.replaceDocument(up.document_id)
    saveFlowState({ active_document_id: up.document_id })
    return { document_id: up.document_id, state: "ready" }
  },

  // 理解创建（资料来源）；后端幂等，同一 Idempotency-Key 重放返回同一结果
  async ensureUnderstanding() {
    const state = loadFlowState()
    if (!state.session_id) throw apiError("会话未创建", "SESSION_NOT_FOUND")
    if (state.understanding_id && state.understanding_revision) {
      return realInputApi.readUnderstanding(state.understanding_id)
    }
    if (!state.active_document_id) {
      throw apiError("资料尚未上传成功，不能进入摘要确认", "SOURCE_NOT_READY")
    }
    const data = await realRequest("/api/v3/understandings", {
      method: "POST",
      data: {
        schema_version: "understanding_v3.1",
        session_id: state.session_id,
        inputs: [
          {
            source_id: state.active_document_id,
            source_type: "document",
            processing_status: "ready",
            text_ref: state.active_document_id,
            captured_at: new Date().toISOString(),
          },
        ],
      },
      headers: { "Idempotency-Key": idempotencyKey() },
    })
    saveFlowState({
      understanding_id: data.understanding_id,
      understanding_revision: data.revision,
      understanding_status: data.status,
    })
    return data
  },

  async readUnderstanding(understandingId) {
    const data = await realRequest("/api/v3/understandings/" + encodeURIComponent(understandingId))
    saveFlowState({
      understanding_id: data.understanding_id,
      understanding_revision: data.revision,
      understanding_status: data.status,
    })
    return data
  },

  // 资料摘要确认页数据：Read Model §4（只暴露用户可理解内容）
  async getCaseSummary() {
    const data = await realInputApi.ensureUnderstanding()
    const cs = data.case_summary
    if (!cs) {
      // 无可用摘要（来源失败等）：不能进入摘要确认（Amendment §3.1）
      throw apiError(
        data.status === "failed"
          ? "资料尚未识别成功，不能进入摘要确认"
          : "资料摘要尚未就绪，请稍后重试。",
        "SOURCE_NOT_READY",
      )
    }
    return {
      page: "case_summary",
      understanding_id: data.understanding_id,
      revision: cs.revision,
      status: cs.status,
      title: cs.title || "请确认资料摘要",
      summary: cs.summary,
      editable_fields: cs.editable_fields || [],
      source_notice: "以下内容是系统根据你上传的资料整理出的简要信息。请确认它是否准确反映你的近期情况。",
      warnings: cs.warnings || [],
    }
  },

  async confirmUnderstanding(payload) {
    const state = loadFlowState()
    if (!state.understanding_id) throw apiError("摘要不存在", "NOT_FOUND")
    const data = await realRequest(
      "/api/v3/understandings/" + encodeURIComponent(state.understanding_id) + "/confirmations",
      {
        method: "POST",
        data: {
          schema_version: "understanding_v3.1",
          expected_revision: payload.expected_revision,
          expected_input_revision: state.input_revision,
          decision: payload.decision,
          changes: payload.changes || [],
          edited_summary_text: payload.edited_summary_text || undefined,
          reprocess_requested: !!payload.reprocess_requested,
        },
        headers: { "Idempotency-Key": idempotencyKey() },
      },
    )
    saveFlowState({
      understanding_revision: data.revision,
      understanding_status: data.status,
      input_revision: data.input_revision || state.input_revision,
    })
    return data
  },

  // 最近情况描述真实提交（narrative 源，inline text）
  // 仅用于无资料流程（without_document）：narrative-only 源创建 Understanding 后
  // 立即确认（decision=confirm），经 CAS 绑定为会话活跃引用并递增 input_revision，
  // 描述自此真正进入评估输入链（Amendment §4）。
  // 有资料流程"已确认摘要 + 追加描述源"为后端缺口（见文件头），由页面本机暂存，
  // 本方法在该路径如实报错，绝不把暂存伪装成已提交。
  async submitNarrative(text) {
    const state = loadFlowState()
    if (!state.session_id) throw apiError("会话未创建", "SESSION_NOT_FOUND")
    const body = String(text || "").trim()
    if (!body) throw apiError("请先填写描述内容", "VALIDATION_ERROR")
    if (state.input_mode === "with_document") {
      throw apiError(
        "当前流程暂不支持提交补充描述，内容已保留在本机，不会丢失。",
        "NARRATIVE_APPEND_UNSUPPORTED",
      )
    }
    const data = await realRequest("/api/v3/understandings", {
      method: "POST",
      data: {
        schema_version: "understanding_v3.1",
        session_id: state.session_id,
        inputs: [
          {
            source_id: "narrative-" + Date.now(),
            source_type: "narrative",
            processing_status: "ready",
            text: body,
            captured_at: new Date().toISOString(),
          },
        ],
      },
      headers: { "Idempotency-Key": idempotencyKey() },
    })
    saveFlowState({
      narrative_submitted: true,
      narrative_text: body,
      understanding_id: data.understanding_id,
      understanding_revision: data.revision,
      understanding_status: data.status,
    })
    // 创建不改变 input_revision（已核实后端语义），随后确认即可绑定会话；
    // 确认失败如实抛错，页面停留重试，不静默降级为本机暂存。
    await realInputApi.confirmUnderstanding({
      expected_revision: data.revision,
      decision: "confirm",
      changes: [],
    })
    return data
  },

  // V3.1 疗愈诉求（选填）：后端暂无对应保存能力 → 本机暂存，如实标注，
  // 不伪造已提交、不补默认偏好；后端交付后在此替换为真实请求
  // 复审（合同校验）：payload 字段与 Read Model §10 一致
  //   primary_goal / secondary_goal / custom_goal_text
  // 不再使用 primary / secondary / custom_text 作为最终字段
  async submitHealingIntent(payload) {
    await delay(60)
    const clean = payload
      ? {
          primary_goal: payload.primary_goal || null,
          secondary_goal: payload.secondary_goal || null,
          custom_goal_text: payload.custom_goal_text || null,
        }
      : null
    if (clean) {
      try { safeSet("v3_healing_intent", JSON.stringify(clean)) } catch (e) { /* ignore */ }
    }
    return { received: true, saved_locally: !!clean }
  },

  async submitFeedback(payload) {
    const state = loadFlowState()
    // feedback_v3.0 必填：music_ref 与 pre_state_snapshot 可由 flow state 补全
    const music = state.music || {}
    const body = Object.assign(
      {
        music_ref: payload.music_ref || music.music_ref,
        pre_state_snapshot:
          payload.pre_state_snapshot || {
            snapshot_id: "snap_" + Date.now(),
            source: "player_session",
            captured_at: new Date().toISOString(),
          },
      },
      payload,
    )
    return realRequest("/api/v3/feedback", {
      method: "POST",
      data: Object.assign({ schema_version: "feedback_v3.0", session_id: state.session_id }, body),
      headers: { "Idempotency-Key": idempotencyKey() },
    })
  },

  async addFavorite(musicId, sourceType) {
    return realRequest("/api/v3/favorites", {
      method: "PUT",
      data: { music_ref: { music_id: musicId, source_type: sourceType } },
    })
  },

  async removeFavorite(musicId) {
    return realRequest("/api/v3/favorites/" + encodeURIComponent(musicId), { method: "DELETE" })
  },

  async getFavorites() {
    return realRequest("/api/v3/favorites")
  },

  async getHistory() {
    return realRequest("/api/v3/me/history")
  },

  async getPreferences() {
    return realRequest("/api/v3/me/preferences")
  },

  // 音乐生成：后端接口已交付，但依赖辨证处方能力（尚未接入）
  async startMusicGeneration() {
    throw agentPendingError("音乐生成")
  },
  async pollMusicGeneration(taskId) {
    const state = loadFlowState()
    const id = taskId || state.task_id
    if (!id) throw agentPendingError("音乐生成任务")
    const task = await realRequest("/api/v3/music/generations/" + encodeURIComponent(id))
    persistMusicTask(task)
    return task
  },
  async cancelMusicGeneration(taskId) {
    const state = loadFlowState()
    const id = taskId || state.task_id
    if (!id) throw agentPendingError("音乐生成任务")
    const task = await realRequest(
      "/api/v3/music/generations/" + encodeURIComponent(id) + "/cancel",
      { method: "POST" },
    )
    persistMusicTask(task)
    return task
  },
}

// 生成任务成功后保存 asset（播放页只播放后端返回的 Music Asset）
function persistMusicTask(task) {
  if (task && (task.status === "succeeded" || task.status === "matched_fallback") && task.audio_asset) {
    saveFlowState({
      task_id: task.task_id,
      music: {
        page: "player",
        music_ref: task.audio_asset.music_ref,
        title: task.audio_asset.title,
        stream_url: task.audio_asset.stream_url,
        duration_seconds: task.audio_asset.duration_seconds,
        source_label: task.status === "matched_fallback" ? "审核曲库匹配音乐" : "AI生成音乐",
        tone_label: toneLabel(task.audio_asset.tone_profile),
        instrument_labels: task.audio_asset.instruments || [],
        disclaimer: "音乐调养不能替代专业医疗或心理帮助。",
      },
    })
  } else if (task && task.task_id) {
    saveFlowState({ task_id: task.task_id })
  }
}

const TONE_LABELS = { jiao: "角音", zhi: "徵音", gong: "宫音", shang: "商音", yu: "羽音" }

function toneLabel(toneProfile) {
  if (!toneProfile) return ""
  const key = toneProfile.dominant_tone || ""
  return (TONE_LABELS[key] || "") + "为主"
}

// ===== Mock 状态机（虚构 fixture；仅供显式 mock/hybrid 模式与自动测试） =====

const MOCK = {
  token: null,
  session: null,
  documents: [], // 多资料：按上传顺序保存 document_id / state / uploaded_at
  document: null, // 最近一份上传的资料（兼容旧读取，仅作为最后活跃资料的别名）
  understanding: null,
  transcript: null,
  questionnaireSubmission: null,
  assessment: null,
  basis: null,
  musicTask: null,
  music: null,
  feedbackDone: false,
  healingIntent: null,
}

function clone(obj) {
  return JSON.parse(JSON.stringify(obj))
}

// ---- mock: 问卷（与后端权威清单 knowledge/v3/questionnaire-v3.0.json 逐字一致） ----
function buildMockQuestionnaireSchema() {
  const schema = clone(QUESTIONNAIRE_MANIFEST)
  schema.page = "questionnaire_v3"
  schema.title = "五脏状态问卷"
  schema.required_for_flow = false // 由 session 权威模式决定（无资料=true）
  schema.skip_action = { id: "skip_questionnaire", label: "跳过问卷，继续评估", style: "link", enabled: true }
  schema.estimated_minutes = 3
  return schema
}

// 当前生效的 input_mode：真实模式读后端同步的 flow state，mock 读内存会话
function getEffectiveInputMode() {
  if (INPUT_REAL) {
    const state = loadFlowState()
    return state.input_mode !== undefined ? state.input_mode : null
  }
  return MOCK.session ? MOCK.session.input_mode : null
}

// hybrid：Agent 段走 mock 状态机，需要一份与真实会话同步的镜像
function ensureMockSession() {
  if (MOCK.session) return MOCK.session
  const st = loadFlowState()
  MOCK.session = {
    session_id: st.session_id || "sess_hybrid_mirror",
    flow_contract_version: "v3-owner-flow-1",
    input_mode: st.input_mode !== undefined ? st.input_mode : null,
    input_revision: st.input_revision || 1,
    active_document_id: st.active_document_id || null,
    understanding_ref: null,
    questionnaire_ref: null,
  }
  return MOCK.session
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
    editable_fields: [],
    source_notice: "以下内容是系统根据你上传的资料整理出的简要信息。请确认它是否准确反映你的近期情况。",
    warnings: [],
  }
}

// ---- mock: 最终评估确认（Read Model §8） ----
function mockAssessment() {
  return {
    page: "assessment_confirmation",
    assessment_id: "asmt_mock_001",
    revision: 1,
    status: "needs_confirmation",
    title: "确认一下我们对你当前状态的理解",
    summary: "近期主要表现为思虑偏多、睡眠恢复不足和白天精力下降。",
    sections: [
      { id: "body", title: "身体感受", items: ["睡眠恢复不足", "白天精力下降"] },
      { id: "context", title: "最近情况", items: ["近期学习/工作安排带来一定压力"] },
    ],
    editable_items: [
      { target_id: "fev_mock_sleep", label: "睡眠恢复不足", value: { type: "severity", value: "moderate" }, allowed_values: ["none", "mild", "moderate", "severe"], required: false },
      { target_id: "fev_mock_energy", label: "白天精力下降", value: { type: "severity", value: "mild" }, allowed_values: ["none", "mild", "moderate", "severe"], required: false },
    ],
    degradation_notice: null,
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
    music_parameters: { bpm: 58, duration_seconds: 300, instrument_labels: ["古琴", "洞箫"], ambient_labels: ["流水"] },
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
    stream_url: "/static/music/jiao-demo.wav", // mock：本地示例音频（仅显式 mock/hybrid 模式）
    duration_seconds: 300,
    source_label: sourceType === "matched" ? "审核曲库匹配音乐" : "AI生成音乐",
    tone_label: "宫音为主",
    instrument_labels: ["古琴", "洞箫"],
    favorite: false,
    disclaimer: "音乐调养不能替代专业医疗或心理帮助。",
  }
}

function delay(ms) {
  return new Promise((r) => setTimeout(r, ms))
}

function stripInternal(obj) {
  const out = clone(obj)
  Object.keys(out).forEach((k) => {
    if (k.indexOf("_") === 0) delete out[k]
  })
  return out
}

const mockApi = {
  async guestAuth() {
    await delay(200)
    MOCK.token = {
      access_token: "mock-token-" + Math.random().toString(36).slice(2),
      token_type: "Bearer",
      expires_at: new Date(Date.now() + 86400000).toISOString(),
      public_user_id: "u_guest_mock",
    }
    safeSet("v3_access_token", MOCK.token.access_token)
    return clone(MOCK.token)
  },

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
    MOCK.documents = []
    MOCK.document = null
    MOCK.understanding = null
    MOCK.questionnaireSubmission = null
    MOCK.assessment = null
    MOCK.basis = null
    MOCK.musicTask = null
    MOCK.music = null
    MOCK.feedbackDone = false
    MOCK.healingIntent = null
    clearFlowState()
    return clone(MOCK.session)
  },

  getSession() {
    if (!MOCK.session) {
      return Promise.reject(apiError("会话未创建", "SESSION_NOT_FOUND"))
    }
    return Promise.resolve(clone(MOCK.session))
  },

  // input-transitions 语义与后端一致：每次切换 input_revision+1
  async inputTransition(action, payload = {}) {
    await delay(300)
    const s = MOCK.session
    if (!s) throw apiError("会话未创建", "SESSION_NOT_FOUND")
    if (action === "select_mode") {
      if (s.input_mode !== null) {
        throw apiError("入口已选择，不能重复选择", "INPUT_REVISION_CONFLICT", { status: 409 })
      }
      s.input_mode = payload.input_mode
      s.input_revision += 1
      return clone(s)
    }
    if (action === "replace_document") {
      if (!payload.document_id) {
        throw apiError("缺少新资料标识", "VALIDATION_ERROR", { status: 422 })
      }
      // 多资料：把新 document 追加进 MOCK.documents，并设为活跃 document
      const exists = (MOCK.documents || []).find((d) => d.document_id === payload.document_id)
      if (!exists) {
        MOCK.documents = MOCK.documents || []
        MOCK.documents.push({
          document_id: payload.document_id,
          state: "ready",
          uploaded_at: new Date().toISOString(),
        })
      }
      MOCK.document = { document_id: payload.document_id, state: "ready", uploaded_at: new Date().toISOString() }
      s.input_mode = "with_document"
      s.input_revision += 1
      s.active_document_id = payload.document_id
      s.understanding_ref = null // 旧摘要失效（Amendment §3.4）
      MOCK.understanding = null
      return clone(s)
    }
    if (action === "discard_document") {
      // 丢弃当前资料：清空多资料集合，重置 active_document_id
      MOCK.documents = []
      MOCK.document = null
      s.input_mode = "without_document"
      s.input_revision += 1
      s.active_document_id = null
      s.understanding_ref = null
      MOCK.understanding = null
      return clone(s)
    }
    throw apiError("未知操作", "VALIDATION_ERROR", { status: 422 })
  },

  async selectMode(inputMode) {
    return mockApi.inputTransition("select_mode", { input_mode: inputMode })
  },

  async discardDocument() {
    return mockApi.inputTransition("discard_document")
  },

  // mock 行为：文件名带 "fail" 时模拟 OCR 失败，否则处理成功
  async uploadDocument(filePath, fileName) {
    await delay(1200)
    const fail = fileName && String(fileName).toLowerCase().indexOf("fail") !== -1
    const docId = "doc_mock_" + Date.now() + "_" + (MOCK.documents || []).length
    const record = {
      document_id: docId,
      state: fail ? "failed" : "ready",
      uploaded_at: new Date().toISOString(),
    }
    // 多资料：追加而非覆盖；保留上传顺序
    MOCK.documents = MOCK.documents || []
    MOCK.documents.push(record)
    MOCK.document = record
    const s = MOCK.session
    if (s && !fail) {
      s.input_mode = "with_document"
      s.input_revision += 1 // replace_document
      s.active_document_id = docId
      s.understanding_ref = null
      MOCK.understanding = null
    }
    return clone(record)
  },

  getCaseSummary() {
    // 多资料：只要至少一份文档达 ready 即可生成摘要（mock 演示）
    const anyReady = (MOCK.documents || []).some((d) => d.state === "ready")
    if (!anyReady && (!MOCK.document || MOCK.document.state !== "ready")) {
      return Promise.reject(apiError("资料尚未识别成功，不能进入摘要确认", "SOURCE_NOT_READY"))
    }
    if (!MOCK.understanding) {
      MOCK.understanding = mockCaseSummary()
      const activeId = MOCK.session && MOCK.session.active_document_id
      MOCK.understanding.source_document_ids = (MOCK.documents || [])
        .filter((d) => d.state === "ready")
        .map((d) => d.document_id)
      MOCK.session.understanding_ref = { understanding_id: "und_mock_001", revision: 1 }
      // 如果没有 active_document_id 但 documents 里有 ready 的，取最后一份
      if (!MOCK.session.active_document_id && MOCK.understanding.source_document_ids.length) {
        MOCK.session.active_document_id = MOCK.understanding.source_document_ids[MOCK.understanding.source_document_ids.length - 1]
      }
    }
    return Promise.resolve(clone(MOCK.understanding))
  },

  async confirmUnderstanding(payload) {
    await delay(500)
    const u = MOCK.understanding
    if (!u) throw apiError("摘要不存在", "NOT_FOUND")
    if (payload.expected_revision !== u.revision) {
      throw apiError("摘要已被更新，请刷新后重试", "REVISION_CONFLICT", { status: 409 })
    }
    if (payload.decision === "confirm") {
      u.status = "confirmed"
      u.revision += 1
      MOCK.session.understanding_ref = { understanding_id: u.understanding_id, revision: u.revision }
      return clone(u)
    }
    if (payload.decision === "confirm_with_changes") {
      const text = (payload.edited_summary_text || "").trim()
      if (!text || text.length > 2000) {
        throw apiError("摘要文本需要 1-2000 字", "VALIDATION_ERROR", { status: 422 })
      }
      u.summary = text
      u.revision += 1
      u.status = "confirmed"
      MOCK.session.understanding_ref = { understanding_id: u.understanding_id, revision: u.revision }
      return clone(u)
    }
    throw apiError("未知确认类型", "VALIDATION_ERROR", { status: 422 })
  },

  // mock：最近情况提交（与真实语义一致——无资料路径创建并绑定 narrative 源理解；
  // 有资料路径后端缺口同样如实报错）
  async submitNarrative(text) {
    await delay(400)
    ensureMockSession()
    const s = MOCK.session
    const body = String(text || "").trim()
    if (!body) throw apiError("请先填写描述内容", "VALIDATION_ERROR")
    if (s.input_mode === "with_document") {
      throw apiError(
        "当前流程暂不支持提交补充描述，内容已保留在本机，不会丢失。",
        "NARRATIVE_APPEND_UNSUPPORTED",
      )
    }
    MOCK.understanding = {
      understanding_id: "und_narrative_" + Date.now(),
      revision: 1,
      status: "confirmed",
      source_type: "narrative",
      text: body,
    }
    s.understanding_ref = { understanding_id: MOCK.understanding.understanding_id, revision: 2 }
    return clone(MOCK.understanding)
  },

  async getQuestionnaireSchema() {
    await delay(200)
    const schema = buildMockQuestionnaireSchema()
    if (getEffectiveInputMode() === "without_document") {
      schema.required_for_flow = true
      schema.skip_action = null
    }
    return schema
  },

  async submitQuestionnaire(answers) {
    await delay(600)
    ensureMockSession()
    const schema = QUESTIONNAIRE_MANIFEST
    // 校验 10 题完整（按题型：频率题需 0-4 整数；多选题需非空数组）
    const missing = schema.questions.filter((q) => {
      const a = answers[q.question_id]
      if (q.answer_type === "frequency_0_4") {
        return typeof a !== "number"
      }
      return !a || !a.length
    })
    if (missing.length) {
      throw apiError("还有 " + missing.length + " 题未作答", "QUESTIONNAIRE_INCOMPLETE", { status: 422 })
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

  async createAssessment() {
    await delay(1500)
    ensureMockSession()
    const s = MOCK.session
    if (s.input_mode === "without_document" && !MOCK.questionnaireSubmission) {
      throw apiError("请先完成 10 道状态问卷", "QUESTIONNAIRE_REQUIRED", { status: 422 })
    }
    MOCK.assessment = mockAssessment()
    return clone(MOCK.assessment)
  },

  getAssessment() {
    if (!MOCK.assessment) {
      return Promise.reject(apiError("评估尚未生成", "NOT_FOUND"))
    }
    return Promise.resolve(clone(MOCK.assessment))
  },

  async confirmAssessment(payload) {
    await delay(500)
    const a = MOCK.assessment
    if (!a) throw apiError("评估不存在", "NOT_FOUND")
    if (payload.expected_revision !== a.revision) {
      throw apiError("评估已被更新，请刷新后重试", "REVISION_CONFLICT", { status: 409 })
    }
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

  async getMusicBasis() {
    await delay(800)
    ensureMockSession()
    if (!MOCK.assessment || MOCK.assessment.status !== "confirmed") {
      throw apiError("请先完成最终确认", "ASSESSMENT_NOT_CONFIRMED", { status: 409 })
    }
    MOCK.basis = mockBasis()
    return clone(MOCK.basis)
  },

  async startMusicGeneration() {
    await delay(300)
    MOCK.musicTask = {
      page: "music_generation",
      task_id: "task_mock_" + Date.now(),
      status: "queued",
      title: "正在生成音乐",
      progress: { value: 0, indeterminate: true }, // 未报告真实进度时不伪造百分比
      message: "正在根据本次音乐参数生成。",
      poll_after_ms: 1200,
      can_cancel: true,
      _elapsed: 0,
    }
    return clone(stripInternal(MOCK.musicTask))
  },

  async pollMusicGeneration() {
    await delay(400)
    const t = MOCK.musicTask
    if (!t) throw apiError("生成任务不存在", "NOT_FOUND")
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
    throw apiError("生成任务不存在", "NOT_FOUND")
  },

  getMusic() {
    if (!MOCK.music) {
      return Promise.reject(apiError("音乐尚未生成完成", "NOT_FOUND"))
    }
    return Promise.resolve(clone(MOCK.music))
  },

  async submitFeedback() {
    await delay(400)
    MOCK.feedbackDone = true
    return { received: true }
  },

  // V3.1 疗愈诉求（选填）：演示状态机记录，不补默认偏好
  // 复审（合同校验）：payload 字段与 Read Model §10 一致
  //   primary_goal / secondary_goal / custom_goal_text
  async submitHealingIntent(payload) {
    await delay(200)
    ensureMockSession()
    MOCK.healingIntent = payload
      ? {
          primary_goal: payload.primary_goal || null,
          secondary_goal: payload.secondary_goal || null,
          custom_goal_text: payload.custom_goal_text || null,
        }
      : null
    return { received: true, saved_locally: !!payload }
  },
}

// ===== 对外接口（按模式分发） =====

// 频率题 0..4 选项标签（权威清单同源，页面渲染 frequency_0_4 题型使用）
export { FREQUENCY_OPTIONS }

export const apiV3 = {
  MODE,
  // hybrid 模式下 Agent 段为 mock 演示数据：页面需显示"演示数据"标识
  AGENT_SIMULATED: MODE === "hybrid",
  // mock 模式下输入段（含语音转写）为模拟数据：real/hybrid 不得产生虚构 transcript
  INPUT_SIMULATED: MODE === "mock",

  guestAuth() {
    return INPUT_REAL ? realInputApi.guestAuth() : mockApi.guestAuth()
  },
  createSession() {
    return INPUT_REAL ? realInputApi.createSession() : mockApi.createSession()
  },
  getSession() {
    return INPUT_REAL ? realInputApi.getSession() : mockApi.getSession()
  },
  selectMode(inputMode) {
    return INPUT_REAL ? realInputApi.selectMode(inputMode) : mockApi.selectMode(inputMode)
  },
  discardDocument() {
    return INPUT_REAL ? realInputApi.discardDocument() : mockApi.discardDocument()
  },
  uploadDocument(filePath, fileName) {
    return INPUT_REAL ? realInputApi.uploadDocument(filePath) : mockApi.uploadDocument(filePath, fileName)
  },
  getCaseSummary() {
    return INPUT_REAL ? realInputApi.getCaseSummary() : mockApi.getCaseSummary()
  },
  confirmUnderstanding(payload) {
    return INPUT_REAL ? realInputApi.confirmUnderstanding(payload) : mockApi.confirmUnderstanding(payload)
  },
  // 最近情况描述：无资料路径真实提交（narrative 源）并确认绑定会话
  submitNarrative(text) {
    return INPUT_REAL ? realInputApi.submitNarrative(text) : mockApi.submitNarrative(text)
  },

  // V3.1 疗愈诉求（选填）：real 本机暂存并如实标注；mock/hybrid 走演示状态机
  submitHealingIntent(payload) {
    return INPUT_REAL ? realInputApi.submitHealingIntent(payload) : mockApi.submitHealingIntent(payload)
  },

  // 问卷：题目为权威清单（前后端同源），三种模式一致，必填性由会话权威模式决定；
  // 提交依赖后端综合评估能力（尚未交付）：real 模式返回等待状态，mock/hybrid 走演示状态机
  getQuestionnaireSchema() {
    return mockApi.getQuestionnaireSchema()
  },
  submitQuestionnaire(answers) {
    if (!AGENT_MOCK) return Promise.reject(agentPendingError("问卷提交与综合评估"))
    return mockApi.submitQuestionnaire(answers)
  },

  // 评估（依赖后端综合评估能力，尚未交付）
  createAssessment() {
    if (!AGENT_MOCK) return Promise.reject(agentPendingError("综合评估"))
    return mockApi.createAssessment()
  },
  getAssessment() {
    if (!AGENT_MOCK) return Promise.reject(agentPendingError("综合评估"))
    return mockApi.getAssessment()
  },
  confirmAssessment(payload) {
    if (!AGENT_MOCK) return Promise.reject(agentPendingError("综合评估"))
    return mockApi.confirmAssessment(payload)
  },

  // 辨证与生成依据（依赖后端辨证能力，尚未交付）
  getMusicBasis() {
    if (!AGENT_MOCK) return Promise.reject(agentPendingError("辨证与音乐生成依据"))
    return mockApi.getMusicBasis()
  },

  // 音乐生成：后端接口已交付但依赖辨证处方能力（尚未接入）→ real 等待状态；
  // mock/hybrid 走演示状态机
  startMusicGeneration() {
    return AGENT_MOCK ? mockApi.startMusicGeneration() : realInputApi.startMusicGeneration()
  },
  pollMusicGeneration(taskId) {
    return AGENT_MOCK ? mockApi.pollMusicGeneration() : realInputApi.pollMusicGeneration(taskId)
  },
  cancelMusicGeneration(taskId) {
    return AGENT_MOCK ? mockApi.cancelMusicGeneration() : realInputApi.cancelMusicGeneration(taskId)
  },

  getMusic() {
    if (!AGENT_MOCK) {
      const state = loadFlowState()
      if (state.music) return Promise.resolve(state.music)
      return Promise.reject(agentPendingError("音乐播放"))
    }
    return mockApi.getMusic()
  },

  // 反馈：真实接口已交付（需要真实 music asset）；mock/hybrid 走演示状态机
  submitFeedback(payload) {
    return INPUT_REAL && !AGENT_MOCK ? realInputApi.submitFeedback(payload) : mockApi.submitFeedback(payload)
  },
  // 收藏等个人数据接口；mock/hybrid 模式下仅本地记录 UI 状态
  addFavorite(musicId, sourceType) {
    if (!INPUT_REAL) return Promise.resolve({ music_ref: { music_id: musicId, source_type: sourceType }, is_favorite: true })
    return realInputApi.addFavorite(musicId, sourceType)
  },
  removeFavorite(musicId) {
    if (!INPUT_REAL) return Promise.resolve({ is_favorite: false })
    return realInputApi.removeFavorite(musicId)
  },
  getFavorites() {
    return INPUT_REAL ? realInputApi.getFavorites() : Promise.resolve({ items: [], total: 0 })
  },
  getHistory() {
    return INPUT_REAL ? realInputApi.getHistory() : Promise.resolve({ items: [], total: 0 })
  },
  getPreferences() {
    return INPUT_REAL ? realInputApi.getPreferences() : Promise.resolve(null)
  },

  // 真实后端音频流地址（相对路径 → 绝对地址）
  musicStreamUrl(streamUrl) {
    if (!streamUrl) return ""
    if (streamUrl.indexOf("/api/") === 0) return BASE_URL + streamUrl
    return streamUrl
  },

  // 播放鉴权（P0-3 前端侧）：后端音频流要求 Bearer 头，audio 标签无法携带。
  // 对后端地址先用带鉴权的 downloadFile 拉取为本地临时文件，再交给播放器；
  // 本地资源与外部直链原样返回。失败时如实报错，不降级为无鉴权直连。
  fetchAuthorizedAudio(streamUrl) {
    if (!streamUrl) return Promise.resolve("")
    const absolute = this.musicStreamUrl(streamUrl)
    if (absolute.indexOf(BASE_URL) !== 0) {
      return Promise.resolve(absolute)
    }
    return new Promise((resolve, reject) => {
      let downloadFile = null
      try {
        downloadFile = uni.downloadFile
      } catch (e) {
        downloadFile = null // uni 不可用（Node 测试环境）
      }
      if (!downloadFile) {
        reject(apiError(FRIENDLY_ERRORS.NETWORK_ERROR, "NETWORK_ERROR"))
        return
      }
      downloadFile({
        url: absolute,
        header: authHeaders(),
        success: (res) => {
          if (res.statusCode >= 200 && res.statusCode < 300 && res.tempFilePath) {
            resolve(res.tempFilePath)
          } else {
            reject(apiError("音频加载失败，请稍后重试", "AUDIO_FETCH_FAILED"))
          }
        },
        fail: () => {
          reject(apiError(FRIENDLY_ERRORS.NETWORK_ERROR, "NETWORK_ERROR"))
        },
      })
    })
  },

  // 会话辅助：页面间共享 session id（真实模式存于 v3_flow_state）
  rememberSession(session) {
    if (session && session.session_id) {
      const state = loadFlowState()
      // mock 模式没有持久 state，仅记录 id
      if (state.session_id !== session.session_id) {
        saveFlowState({
          session_id: session.session_id,
          input_revision: session.input_revision || 1,
          input_mode: session.input_mode !== undefined ? session.input_mode : null,
          active_document_id: session.active_document_id || null,
        })
      }
    }
  },

  // 测试/调试辅助
  __resetForTest() {
    clearFlowState()
    MOCK.token = null
    MOCK.session = null
    MOCK.documents = []
    MOCK.document = null
    MOCK.understanding = null
    MOCK.questionnaireSubmission = null
    MOCK.assessment = null
    MOCK.basis = null
    MOCK.musicTask = null
    MOCK.music = null
    MOCK.feedbackDone = false
    MOCK.healingIntent = null
  },
}

export default apiV3
