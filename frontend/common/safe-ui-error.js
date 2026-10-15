const SAFE_MESSAGES = {
  BACKEND_UNAVAILABLE: '服务暂时不可用，请稍后重试。',
  OCR_ENGINE_UNAVAILABLE: 'OCR 服务暂时不可用，请重试、手动输入或跳过。',
  OCR_FAILED: 'OCR 识别失败，请重试、手动输入或跳过。',
  OCR_TIMEOUT: 'OCR 识别超时，请重试、手动输入或跳过。',
  ASSESSMENT_FAILED: '状态评估暂时不可用，请稍后重试。',
  FOLLOW_UP_FAILED: '补充信息提交失败，请重试。',
  CONFIRMATION_FAILED: '确认失败，已保留你的内容，请重试。',
  WORKFLOW_FAILED: 'AI 分析暂时不可用，请稍后重试。',
  MUSIC_MATCH_FAILED: '暂时没有匹配到可播放音乐，请稍后重试。',
  NO_MUSIC: '暂时没有匹配到可播放音乐，请返回补充信息。',
  SAFETY_VERIFICATION_FAILED: '安全信息核验未完成，请重试。',
  COMFORT_AUDIO_FAILED: '安抚音频暂时不可用，请稍后重试。',
}

export function safeUiError(error, fallbackCode = 'BACKEND_UNAVAILABLE') {
  const code = error?.code && SAFE_MESSAGES[error.code] ? error.code : fallbackCode
  return { code, message: SAFE_MESSAGES[code] || SAFE_MESSAGES.BACKEND_UNAVAILABLE }
}
