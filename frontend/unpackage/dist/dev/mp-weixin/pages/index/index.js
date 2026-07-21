"use strict";
const common_vendor = require("../../common/vendor.js");
const _sfc_main = {
  data() {
    return {
      userName: "用户",
      todayDate: "",
      hasPrescription: false,
      todayPrescription: null
    };
  },
  onLoad() {
    const now = /* @__PURE__ */ new Date();
    const month = now.getMonth() + 1;
    const day = now.getDate();
    const weekDays = ["日", "一", "二", "三", "四", "五", "六"];
    const week = weekDays[now.getDay()];
    this.todayDate = `${month}月${day}日 星期${week}`;
  },
  methods: {
    goEmotion() {
      common_vendor.index.navigateTo({ url: "/pages/emotion/emotion" });
    },
    goPlayer() {
      common_vendor.index.switchTab({ url: "/pages/player/player" });
    }
  }
};
function _sfc_render(_ctx, _cache, $props, $setup, $data, $options) {
  return common_vendor.e({
    a: common_vendor.t($data.userName),
    b: common_vendor.t($data.todayDate),
    c: $data.hasPrescription
  }, $data.hasPrescription ? {
    d: common_vendor.o((...args) => $options.goPlayer && $options.goPlayer(...args), "02")
  } : {}, {
    e: common_vendor.o((...args) => $options.goEmotion && $options.goEmotion(...args), "e9")
  });
}
const MiniProgramPage = /* @__PURE__ */ common_vendor._export_sfc(_sfc_main, [["render", _sfc_render], ["__scopeId", "data-v-1cf27b2a"]]);
wx.createPage(MiniProgramPage);
//# sourceMappingURL=../../../.sourcemap/mp-weixin/pages/index/index.js.map
