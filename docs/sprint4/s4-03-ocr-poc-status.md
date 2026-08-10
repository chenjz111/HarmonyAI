# S4-03 OCR POC Status

- Status: **MANUAL_POC_PENDING**
- Reason: 仓库中没有可合法使用且已脱敏的真实医疗材料。
- Runtime: 安装 `requirements-ocr.txt` 后执行人工 POC。
- Completed automatically: JPG/PNG/PDF 输入校验、PDF 分页、加密检测、block/page confidence、OCR 不可用与失败降级测试。
- Manual gate: 由团队提供 5 份合法、脱敏材料，在安装 PaddleOCR 的环境中记录识别准确率；不得使用伪造结果代替。
