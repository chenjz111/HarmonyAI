"use strict";
const common_vendor = require("../../common/vendor.js");
const _sfc_main = {
  data() {
    return {
      emotions: [
        { id: "nu", name: "怒", element: "木", tone: "角", color: "#4A9D6E", desc: "烦躁易怒、胸闷胁痛", bg: "#E1F5EE" },
        { id: "xi", name: "喜", element: "火", tone: "徵", color: "#E25C4E", desc: "亢奋失眠、心悸不安", bg: "#FAECE7" },
        { id: "si", name: "思", element: "土", tone: "宫", color: "#E8B547", desc: "思虑过度、食欲不振", bg: "#FAEEDA" },
        { id: "bei", name: "悲", element: "金", tone: "商", color: "#9CA8B8", desc: "情绪低落、气短乏力", bg: "#F1EFE8" },
        { id: "kong", name: "恐", element: "水", tone: "羽", color: "#3B5067", desc: "焦虑恐惧、腰膝酸软", bg: "#E6F1FB" }
      ],
      selectedId: ""
    };
  },
  methods: {
    selectEmotion(item) {
      this.selectedId = item.id;
      setTimeout(() => {
        common_vendor.index.navigateTo({
          url: `/pages/survey/survey?emotion=${item.id}&tone=${item.tone}`
        });
      }, 300);
    }
  }
};
function _sfc_render(_ctx, _cache, $props, $setup, $data, $options) {
  return {
    a: common_vendor.f($data.emotions, (item, k0, i0) => {
      return common_vendor.e({
        a: common_vendor.t(item.name),
        b: common_vendor.t(item.tone),
        c: item.color,
        d: common_vendor.t(item.element),
        e: common_vendor.t(item.tone),
        f: common_vendor.t(item.desc),
        g: $data.selectedId === item.id
      }, $data.selectedId === item.id ? {} : {}, {
        h: item.id,
        i: $data.selectedId === item.id ? 1 : "",
        j: item.bg,
        k: $data.selectedId === item.id ? item.color : "transparent",
        l: common_vendor.o(($event) => $options.selectEmotion(item), item.id)
      });
    })
  };
}
const MiniProgramPage = /* @__PURE__ */ common_vendor._export_sfc(_sfc_main, [["render", _sfc_render], ["__scopeId", "data-v-812ea447"]]);
wx.createPage(MiniProgramPage);
//# sourceMappingURL=../../../.sourcemap/mp-weixin/pages/emotion/emotion.js.map
