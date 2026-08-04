const STORAGE_KEY = "harmonyai_sprint3_session"


export function getSprint3Session() {
  return uni.getStorageSync(STORAGE_KEY) || {}
}


export function updateSprint3Session(patch) {
  const next = { ...getSprint3Session(), ...patch }
  uni.setStorageSync(STORAGE_KEY, next)
  return next
}


export function clearSprint3Session() {
  uni.removeStorageSync(STORAGE_KEY)
}
