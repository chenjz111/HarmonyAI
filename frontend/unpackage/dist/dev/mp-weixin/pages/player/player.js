"use strict";
const common_vendor = require("../../common/vendor.js");
const common_api = require("../../common/api.js");
const _sfc_main = {
  data() {
    return {
      // 页面状态：loading / success / error
      status: "loading",
      errorMsg: "",
      // 评估结果（从本地存储读取）
      assessment: null,
      // 播放状态
      isPlaying: false,
      currentTime: "0:00",
      totalTime: "3:45",
      progress: 0,
      // 评分
      rating: 0,
      stars: [1, 2, 3, 4, 5],
      // 处方信息
      prescription: {
        toneName: "角调",
        toneWeight: "75%",
        instrument: "古筝",
        bpm: 68,
        reasoning: "肝郁化火 → 角调疏肝理气，辅以宫调健脾安神",
        syndrome: "肝郁化火"
      }
    };
  },
  onShow() {
    this.loadAssessment();
  },
  methods: {
    loadAssessment() {
      try {
        const data = common_vendor.index.getStorageSync("harmony_latest_assessment");
        if (data) {
          this.assessment = JSON.parse(data);
          this.updatePrescriptionByAssessment(this.assessment);
          this.status = "success";
        } else {
          this.status = "success";
        }
      } catch (e) {
        common_vendor.index.__f__("error", "at pages/player/player.vue:48", "读取评估结果失败：", e);
        this.status = "error";
        this.errorMsg = "读取评估结果失败";
      }
    },
    updatePrescriptionByAssessment(assessment) {
      const tone = assessment.recommended_tone || "角";
      const toneMap = {
        "角": { name: "角调", instrument: "古筝", syndrome: "肝郁化火", reasoning: "角调疏肝理气，辅以宫调健脾安神" },
        "徵": { name: "徵调", instrument: "笛子", syndrome: "心火旺盛", reasoning: "徵调清心降火，辅以羽调滋水涵木" },
        "宫": { name: "宫调", instrument: "埙", syndrome: "脾虚湿困", reasoning: "宫调健脾化湿，辅以商调宣肺理气" },
        "商": { name: "商调", instrument: "编钟", syndrome: "肺气不足", reasoning: "商调补肺益气，辅以宫调培土生金" },
        "羽": { name: "羽调", instrument: "古琴", syndrome: "肾阳不足", reasoning: "羽调温补肾阳，辅以角调疏肝解郁" }
      };
      const info = toneMap[tone] || toneMap["角"];
      const weights = assessment.tone_weights || { "角": 0.75 };
      const mainWeight = Math.round((weights[tone] || 0.75) * 100);
      this.prescription.toneName = info.name;
      this.prescription.toneWeight = mainWeight + "%";
      this.prescription.instrument = info.instrument;
      this.prescription.syndrome = info.syndrome;
      this.prescription.reasoning = info.reasoning;
    },
    togglePlay() {
      this.isPlaying = !this.isPlaying;
      if (this.isPlaying) {
        common_vendor.index.showToast({ title: "播放中（mock）", icon: "none" });
      }
    },
    setRating(star) {
      this.rating = star;
    },
    async submitFeedback() {
      if (this.rating === 0) {
        common_vendor.index.showToast({ title: "请先评分", icon: "none" });
        return;
      }
      try {
        await common_api.submitFeedback({
          rating: this.rating,
          assessment_id: this.assessment ? "mock-assessment-id" : "",
          completed: true
        });
        common_vendor.index.showToast({ title: "感谢您的反馈！", icon: "success" });
        setTimeout(() => {
          common_vendor.index.switchTab({ url: "/pages/index/index" });
        }, 1500);
      } catch (err) {
        common_vendor.index.__f__("error", "at pages/player/player.vue:96", "提交反馈失败：", err);
        common_vendor.index.showToast({ title: "提交失败，请重试", icon: "none" });
      }
    },
    reAssess() {
      common_vendor.index.navigateTo({ url: "/pages/emotion/emotion" });
    }
  }
};
function _sfc_render(_ctx, _cache, $props, $setup, $data, $options) {
  return common_vendor.e({
    a: $data.status === "loading"
  }, $data.status === "loading" ? {} : {}, {
    b: $data.status === "error"
  }, $data.status === "error" ? {
    c: common_vendor.t($data.errorMsg),
    d: common_vendor.o((...args) => $options.loadAssessment && $options.loadAssessment(...args), "e9")
  } : {}, {
    e: $data.status === "success"
  }, $data.status === "success" ? common_vendor.e({
    f: common_vendor.t($data.prescription.toneName),
    g: common_vendor.t($data.prescription.toneWeight),
    h: common_vendor.t($data.prescription.syndrome),
    i: common_vendor.t($data.prescription.instrument),
    j: common_vendor.t($data.prescription.bpm),
    k: common_vendor.t($data.prescription.reasoning),
    l: common_vendor.t($data.isPlaying ? "❚❚" : "▶"),
    m: $data.isPlaying ? 1 : "",
    n: common_vendor.o((...args) => $options.togglePlay && $options.togglePlay(...args), "44"),
    o: $data.progress + "%",
    p: common_vendor.t($data.currentTime),
    q: common_vendor.t($data.totalTime),
    r: common_vendor.f($data.stars, (star, k0, i0) => {
      return {
        a: star,
        b: star <= $data.rating ? 1 : "",
        c: common_vendor.o(($event) => $options.setRating(star), star)
      };
    }),
    s: $data.rating > 0
  }, $data.rating > 0 ? {
    t: common_vendor.t(["", "不太满意", "一般", "还行", "不错", "非常疗愈"][$data.rating])
  } : {}, {
    v: common_vendor.o((...args) => $options.submitFeedback && $options.submitFeedback(...args), "95"),
    w: common_vendor.o((...args) => $options.reAssess && $options.reAssess(...args), "09")
  }) : {});
}
const MiniProgramPage = /* @__PURE__ */ common_vendor._export_sfc(_sfc_main, [["render", _sfc_render], ["__scopeId", "data-v-0391012f"]]);
wx.createPage(MiniProgramPage);
//# sourceMappingURL=../../../.sourcemap/mp-weixin/pages/player/player.js.map
