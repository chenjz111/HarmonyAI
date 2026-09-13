# Homepage return verification

## Finding

The original browser test waited only for the target URL, then immediately called browser back. It could run before the uni-app page finished mounting. In that condition, the URL returned to entry while the questionnaire DOM remained visible, with `Cannot read properties of undefined (reading '$page')`. This was not the previous server-side `entry already selected` message.

The minimal test correction waits until the target page's visible action (`开始识别` or `下一题`) is rendered before returning. No product routing or business code was changed in this diagnosis.

## Verification

- Two consecutive local Edge headless demo runs passed document -> home -> questionnaire -> home -> document -> home, followed by My upgrade placeholder.
- Both successful runs assert no browser page errors.
- 320/360/390/430 and 900px screenshots were captured. No horizontal overflow; desktop canvas remains 430px.
- `git diff --check` passes (line-ending normalization warnings only).
- Earlier homepage implementation focused suites: 70 passed; H5 build passed.

## Limits

This verifies returning after the destination page is ready. The ultra-early browser-back/mount race is observed but not fixed in framework code. No claim is made that arbitrary back presses during initial navigation, Android hardware back, or production API mode have been validated.

Owner next step: inspect homepage at `http://127.0.0.1:5181/?harmonyai_demo=1#/pages/entry/entry`. Other page artwork is deliberately paused. No commit, push, merge, backend changes or paid AI calls in this diagnosis.
