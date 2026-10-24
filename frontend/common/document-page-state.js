const SAFE_OCR_MESSAGES = {
  OCR_ENGINE_UNAVAILABLE: 'OCR 服务暂时不可用，请重试、手动输入或跳过。',
  OCR_TIMEOUT: 'OCR 识别超时，请重试、手动输入或跳过。',
  OCR_FAILED: 'OCR 识别失败，请重试、手动输入或跳过。',
}

export function createDocumentPageState() {
  return { mode: 'idle', text: '', errorCode: '', message: '', editorVisible: false, canConfirm: false, navigateAssessment: false }
}

export function applyOcrResponse(current, response = {}) {
  const status = response.status || response.ocr_status
  if (status === 'failed') {
    const errorCode = response.error_code || response.degradation?.reason_code || 'OCR_FAILED'
    return { ...current, mode: 'failed', text: '', errorCode, message: SAFE_OCR_MESSAGES[errorCode] || SAFE_OCR_MESSAGES.OCR_FAILED, editorVisible: false, canConfirm: false, navigateAssessment: false }
  }
  if (status === 'degraded') {
    return { ...current, mode: 'degraded', text: response.extracted_text || '', errorCode: response.error_code || response.degradation?.reason_code || '', message: 'OCR 仅识别出部分内容，请核对后确认。', editorVisible: true, canConfirm: true, navigateAssessment: false }
  }
  return { ...current, mode: 'success', text: response.extracted_text || '', errorCode: '', message: '', editorVisible: true, canConfirm: true, navigateAssessment: false }
}

export function enterManualMode(current) {
  return { ...current, mode: 'manual', text: current.text || '', message: '请手动输入材料中的相关文字。', editorVisible: true, canConfirm: true, navigateAssessment: false }
}

export function documentActions(state) {
  if (state.mode === 'failed') return ['retry', 'manual', 'skip']
  if (state.mode === 'degraded') return ['confirm', 'retry', 'manual', 'skip']
  if (state.mode === 'manual' || state.mode === 'success') return ['confirm', 'retry', 'skip']
  return []
}
