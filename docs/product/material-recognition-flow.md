# Material Recognition Flow

Status: FROZEN

## State flow

PICKING
-> UPLOADING
-> READING
-> EXTRACTING
-> SUMMARIZING
-> SUMMARY_READY

## Product invariants

1. 上传、识别、摘要属于同一个视觉页面。
2. 点击“开始识别”后禁止成功路径 page navigation。
3. 已上传图片在 processing 阶段持续显示。
4. 已上传图片在 SUMMARY_READY 阶段持续显示。
5. processing 出现在上传图片下方。
6. summary 继续出现在同一页面下方。
7. processing 开始后隐藏：
   - 删除按钮
   - 继续添加
   - 数量提示
   - 开始识别
8. processing 阶段禁止修改上传集合。
9. 摘要继续使用渐进 reveal。
10. SUMMARY_READY 显示：
    - 摘要基本准确，继续下一步
    - 修改资料摘要
    - 重新上传资料
11. 只有确认摘要后才能进入 supplement。
12. OCR / 网络失败可以进入独立 error page。
13. 不允许重新恢复独立 analyzing / summary production flow。
14. 图片是整个识别流程的视觉 anchor。

## Acceptance Criteria

### AC-01

开始识别后 route 不变化。

### AC-02

READING / EXTRACTING / SUMMARIZING 状态仍然显示上传图片。

### AC-03

processing 状态隐藏删除按钮。

### AC-04

processing 状态隐藏继续添加。

### AC-05

processing 状态隐藏数量提示。

### AC-06

processing 状态隐藏开始识别。

### AC-07

SUMMARY_READY 仍显示上传图片。

### AC-08

SUMMARY_READY 显示渐进摘要。

### AC-09

SUMMARY_READY 显示三个操作按钮。

### AC-10

只有确认摘要后进入 supplement。

### AC-11

重新上传恢复 PICKING。

### AC-12

真机视觉表现必须为“同页向下展开”，不能只是 technically same route 但主体互斥整屏替换。

## Authority

如果旧代码、旧测试、旧 Demo 或聊天记忆与本文档冲突，以此 Frozen Spec 为准。
