"use strict";
require("./vendor.js");
function submitAssessment(answers) {
  {
    return mockRequest({
      anxiety_score: 82,
      sleep_score: 40,
      body_score: 65,
      syndrome: "肝郁化火",
      confidence: 0.78,
      recommended_tone: "角",
      tone_weights: { "角": 0.75, "宫": 0.15, "羽": 0.1 }
    });
  }
}
function submitFeedback(feedback) {
  {
    return mockRequest({ success: true });
  }
}
function mockRequest(data) {
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve(data);
    }, 800);
  });
}
exports.submitAssessment = submitAssessment;
exports.submitFeedback = submitFeedback;
//# sourceMappingURL=../../.sourcemap/mp-weixin/common/api.js.map
