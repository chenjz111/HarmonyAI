/**
 * Sprint 7 M1 / FE-2B — Music Library 真实 transport（uni.request 适配）
 *
 * 职责：把 `createMusicLibraryApi({ request })` 需要的 request 适配到 uni.request，
 * 并统一 V3 envelope 解析（成功 { ok, data } / 失败 { ok:false, error:{ code } }）。
 *
 * 边界（Issue #153）：
 *   - 只做传输，不做身份创建、不做生成调用、不做持久缓存
 *   - 后端错误码原样透传，不发明字段或错误码
 *   - 未注入可用 uni 时返回本地 TRANSPORT_UNAVAILABLE，绝不静默返回假数据
 *   - 真实启用仍需 Backend API + owner 隔离 + stream 安全 Gate（见 MUSIC_LIBRARY_LIVE_ENABLED）
 */

// 真实启用开关：默认关闭（fail-closed）。开启需显式注入 true 且通过 Backend Gate。
import { readRuntimeV3Credential, hasAccountRuntime, prepareAccountRequest } from './auth-runtime.js'
export const MUSIC_LIBRARY_LIVE_ENABLED = false

/** Read the actual V3 bearer credential, never the public owner identifier. */
export function readV3AccessToken(uniApi = null) {
  let source = uniApi
  if (!source) {
    try { if (typeof uni !== "undefined") source = uni } catch (e) { return "" }
  }
  if (!source || typeof source.getStorageSync !== "function") return ""
  return readRuntimeV3Credential(source)
}

// 本地传输错误码（非后端合同错误码，仅表示前端环境/网络问题）
export const TRANSPORT_ERROR = Object.freeze({
  UNAVAILABLE: "TRANSPORT_UNAVAILABLE",
  NETWORK: "NETWORK_ERROR",
  AUTH_REQUIRED: "IDENTITY_REQUIRED",
})

function resolveBaseUrl(explicit) {
  if (explicit) return explicit
  try {
    if (import.meta && import.meta.env && import.meta.env.VITE_API_BASE_URL) {
      return import.meta.env.VITE_API_BASE_URL
    }
  } catch (e) {
    /* import.meta 不可用（Node 测试环境） */
  }
  return "http://localhost:8000"
}

function resolveUni(explicit) {
  if (explicit) return explicit
  try {
    if (typeof uni !== "undefined" && uni && typeof uni.request === "function") return uni
  } catch (e) {
    /* uni 未定义 */
  }
  return null
}

/**
 * 创建 uni.request transport。
 *
 * @param {object} [options]
 * @param {string} [options.baseUrl]
 * @param {() => string} [options.getAccessToken] 读取当前访问令牌（不创建身份）
 * @param {object} [options.uniApi] 注入 uni（测试用）
 * @returns {(args: {method: string, path: string, data?: object}) => Promise<{data?: object, error?: {code: string, message: string}}>}
 */
export function createUniMusicLibraryTransport({ baseUrl, getAccessToken, uniApi, prepareAuthentication=true } = {}) {
  const base = resolveBaseUrl(baseUrl)
  const uniRef = resolveUni(uniApi)
  const readToken = typeof getAccessToken === "function" ? getAccessToken : () => ""

  return async function request({ method, path, data, idempotencyKey }) {
    if (prepareAuthentication && hasAccountRuntime(uniRef)) {
      try {
        const owner=uniRef.getStorageSync('v3_public_user_id'),epoch=uniRef.getStorageSync('v3_auth_epoch'),token=readToken()
        await prepareAccountRequest(uniRef)
        if (owner!==uniRef.getStorageSync('v3_public_user_id') || epoch!==uniRef.getStorageSync('v3_auth_epoch') || token!==readToken()) {
          return {error:{code:owner===uniRef.getStorageSync('v3_public_user_id')?'AUTH_REFRESHED':'OWNER_CHANGED',message:'身份状态已更新，请重试；本次操作尚未发送'}}
        }
      } catch(error) {return {error:{code:error.code||TRANSPORT_ERROR.NETWORK,message:'身份暂时无法确认，请重新认证或重试'}}}
    }
    return new Promise((resolve) => {
      if (!uniRef || typeof uniRef.request !== "function") {
        resolve({ error: { code: TRANSPORT_ERROR.UNAVAILABLE, message: "网络能力不可用" } })
        return
      }
      let header = { "Content-Type": "application/json" }
      let token = ""
      try { token = readToken() } catch (e) { token = "" }
      if (typeof token !== "string" || !token.trim()) {
        resolve({ error: { code: TRANSPORT_ERROR.AUTH_REQUIRED, message: "请重新登录后重试" } })
        return
      }
      header = Object.assign(header, { Authorization: "Bearer " + token })
      if (idempotencyKey !== undefined) {
        if (typeof idempotencyKey !== 'string' || !idempotencyKey.trim() || idempotencyKey.length > 128) {
          resolve({error:{code:'IDEMPOTENCY_KEY_REQUIRED',message:'需要提供合法幂等键'}})
          return
        }
        header['Idempotency-Key'] = idempotencyKey
      }
      const args = { url: base + path, method, header }
      if (data !== undefined) args.data = data
      try {
        uniRef.request(
          Object.assign({}, args, {
            success(res) {
              const body = res && res.data ? res.data : {}
              const ok = res && res.statusCode >= 200 && res.statusCode < 300
              if (ok && body.ok === true && Object.hasOwn(body, "data")) {
                resolve({ data: body.data })
                return
              }
              // 失败：透传后端错误码，不发明
              const err = body.error || {}
              resolve({
                error: {
                  code: err.code || "REQUEST_FAILED",
                  message: err.message || "请求未完成，请刷新后重试",
                },
              })
            },
            fail() {
              resolve({ error: { code: TRANSPORT_ERROR.NETWORK, message: "网络连接失败，请检查网络后重试" } })
            },
          })
        )
      } catch (e) {
        resolve({ error: { code: TRANSPORT_ERROR.NETWORK, message: "网络连接失败，请检查网络后重试" } })
      }
    })
  }
}

/**
 * 组装 Music Library API（transport + owner 读取），默认 fail-closed。
 * 仅在显式 `liveEnabled === true` 时才可能真实调用。
 *
 * @param {object} options
 * @param {object} options.createApi createMusicLibraryApi 工厂（注入以避免循环依赖）
 * @param {() => string|null} options.getOwnerId
 * @param {boolean} [options.liveEnabled]
 * @param {object} [options.transportOptions]
 */
export function createLiveMusicLibraryApi({ createApi, getOwnerId, liveEnabled = MUSIC_LIBRARY_LIVE_ENABLED, transportOptions = {} } = {}) {
  if (typeof createApi !== "function") {
    throw new TypeError("createLiveMusicLibraryApi: createApi is required")
  }
  const request = createUniMusicLibraryTransport(transportOptions)
  return createApi({ request, getOwnerId, enabled: liveEnabled === true })
}
