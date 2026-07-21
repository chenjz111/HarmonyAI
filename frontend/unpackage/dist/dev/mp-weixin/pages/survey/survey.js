"use strict";
const common_vendor = require("../../common/vendor.js");
const common_api = require("../../common/api.js");
const _sfc_main = {
  data() {
    return {
      emotion: "",
      tone: "",
      // 页面状态：idle（初始） / loading（分析中） / error（出错）
      status: "idle",
      errorMsg: "",
      currentStep: 1,
      totalSteps: 3,
      steps: [
        {
          title: "情绪状态",
          questions: [
            "我经常感到焦虑不安",
            "我容易因为小事发脾气",
            "我感到情绪低落",
            "我对事物失去兴趣",
            "我感到烦躁无法平静",
            "我容易紧张出汗",
            "我感到孤独无助",
            "我难以控制自己的情绪",
            "我经常感到恐惧",
            "我对未来感到悲观",
            "我容易冲动做事",
            "我感到精神疲惫"
          ]
        },
        {
          title: "睡眠质量",
          questions: [
            "我难以入睡",
            "我半夜容易醒来",
            "我早上醒得太早",
            "我觉得睡眠不够深",
            "我做很多梦",
            "我醒来后仍感到疲倦",
            "我白天容易犯困",
            "我需要很长时间才能入睡"
          ]
        },
        {
          title: "身体状况",
          questions: [
            "我经常头痛",
            "我食欲不振",
            "我消化不良",
            "我经常便秘或腹泻",
            "我感到胸闷气短",
            "我腰膝酸软",
            "我手脚冰凉",
            "我容易出汗",
            "我口干口苦",
            "我视力模糊或眼睛干涩"
          ]
        }
      ],
      // 答案存储：所有题目答案，1-5分
      answers: {},
      // Likert 量表选项
      options: [
        { value: 1, label: "完全不像我" },
        { value: 2, label: "不太像我" },
        { value: 3, label: "一般" },
        { value: 4, label: "有点像我" },
        { value: 5, label: "非常像我" }
      ]
    };
  },
  onLoad(options) {
    this.emotion = options.emotion || "";
    this.tone = options.tone || "";
  },
  computed: {
    currentQuestions() {
      return this.steps[this.currentStep - 1].questions;
    },
    currentTitle() {
      return this.steps[this.currentStep - 1].title;
    },
    progress() {
      return Math.round(this.currentStep / this.totalSteps * 100);
    },
    canSubmit() {
      const currentQs = this.currentQuestions;
      for (let i = 0; i < currentQs.length; i++) {
        const key = `step${this.currentStep}_q${i}`;
        if (!this.answers[key])
          return false;
      }
      return true;
    }
  },
  methods: {
    selectAnswer(questionIndex, value) {
      const key = `step${this.currentStep}_q${questionIndex}`;
      this.answers[key] = value;
    },
    getSelected(questionIndex) {
      const key = `step${this.currentStep}_q${questionIndex}`;
      return this.answers[key] || 0;
    },
    nextStep() {
      if (!this.canSubmit) {
        common_vendor.index.showToast({
          title: "请完成所有题目",
          icon: "none"
        });
        return;
      }
      if (this.currentStep < this.totalSteps) {
        this.currentStep++;
      } else {
        this.submitSurvey();
      }
    },
    prevStep() {
      if (this.currentStep > 1) {
        this.currentStep--;
      }
    },
    async submitSurvey() {
      this.status = "loading";
      try {
        const assessment = await common_api.submitAssessment({
          emotion: this.emotion,
          tone: this.tone,
          answers: this.answers
        });
        common_vendor.index.setStorageSync("harmony_latest_assessment", JSON.stringify(assessment));
        this.status = "success";
        common_vendor.index.switchTab({
          url: "/pages/player/player"
        });
      } catch (err) {
        common_vendor.index.__f__("error", "at pages/survey/survey.vue:147", "提交失败：", err);
        this.status = "error";
        this.errorMsg = "分析失败，请检查网络后重试";
        common_vendor.index.showToast({
          title: "分析失败，请重试",
          icon: "none"
        });
      }
    },
    retry() {
      this.status = "idle";
      this.errorMsg = "";
      this.submitSurvey();
    }
  }
};
function _sfc_render(_ctx, _cache, $props, $setup, $data, $options) {
  return common_vendor.e({
    a: $data.status !== "loading"
  }, $data.status !== "loading" ? {
    b: $options.progress + "%",
    c: common_vendor.t($data.currentStep),
    d: common_vendor.t($data.totalSteps),
    e: common_vendor.t($options.currentTitle)
  } : {}, {
    f: $data.status === "idle" || $data.status === "error"
  }, $data.status === "idle" || $data.status === "error" ? {
    g: common_vendor.f($options.currentQuestions, (question, index, i0) => {
      return {
        a: common_vendor.t(index + 1),
        b: common_vendor.t(question),
        c: common_vendor.f($data.options, (opt, k1, i1) => {
          return {
            a: common_vendor.t(opt.value),
            b: common_vendor.t(opt.label),
            c: opt.value,
            d: $options.getSelected(index) === opt.value ? 1 : "",
            e: common_vendor.o(($event) => $options.selectAnswer(index, opt.value), opt.value)
          };
        }),
        d: index
      };
    })
  } : {}, {
    h: $data.status === "loading"
  }, $data.status === "loading" ? {} : {}, {
    i: $data.status === "error"
  }, $data.status === "error" ? {
    j: common_vendor.t($data.errorMsg),
    k: common_vendor.o((...args) => $options.retry && $options.retry(...args), "8f")
  } : {}, {
    l: $data.status === "idle" || $data.status === "error"
  }, $data.status === "idle" || $data.status === "error" ? {
    m: $data.currentStep === 1 ? 1 : "",
    n: common_vendor.o((...args) => $options.prevStep && $options.prevStep(...args), "82"),
    o: common_vendor.t($data.currentStep < $data.totalSteps ? "下一步" : "提交评估"),
    p: common_vendor.o((...args) => $options.nextStep && $options.nextStep(...args), "93")
  } : {});
}
const MiniProgramPage = /* @__PURE__ */ common_vendor._export_sfc(_sfc_main, [["render", _sfc_render], ["__scopeId", "data-v-21101f15"]]);
wx.createPage(MiniProgramPage);
//# sourceMappingURL=../../../.sourcemap/mp-weixin/pages/survey/survey.js.map
