# Homepage reference sample continuation

Scope: finish only the homepage visual sample from the Owner's supplied image before expanding the remaining page artwork. Preserve all existing uncommitted work. No backend, contract, questionnaire, medical asset, paid provider calls, commit, push or merge.

## Task 1: Homepage and navigation

Use real Vue/uni-app components, not screenshot hotspots. Modify entry.vue, pages.json, relevant frontend tests and new navigation assets only. Preserve onShow -> init -> createSession/rememberSession and choose -> selectMode -> navigateTo; preserve loading/error/retry and submission guard. Do not alter API calls.

Reference: C:/Users/ASUS/AppData/Local/Temp/codex-clipboard-dd3a0a15-69b4-435a-8602-fe7c41eb3d60.png. Inner content only; no device bezel, fake clock/battery or home indicator. Mint paper watercolor with notes/pipa above and flute/guzheng below. Prepared background: /static/v31-home/home-watercolor-v1.png. Controller is preparing /static/v31-home/home-icons-v2.png: a 3:1 sprite of three equal square cells (jade waveform logo, mint medical upload illustration, gold questionnaire illustration). Render using background-size 300% 100%; positions 0/50/100%; round logo and circle-clip card icons. Do not use v1: baked checkerboard is invalid.

Centered logo around 60px, HarmonyAI Georgia 26px, tagline 中医灵感 · 音乐疗愈 at 13px. Slogan 让音乐，陪你回到更好的自己 in KaiTi around 18px with short brush underline. Subtitle 以中医为本 · 用音乐疗愈身心 at 13px. Two cards: 我有就诊资料 / 上传资料, 我没有就诊资料 / 填写问卷. Card icon left about 92px; title 21px bold; subtitle 17px gray; chevron on small tinted circle right. Full-width supporting description below card row, 12px muted. Card1 white/mint and card2 warm cream, thick white border, soft shadow, 23px radius, about 140px tall. Footer MUSIC HEALS A BETTER YOU with landscape visible below. Match image composition at 390px, reflow 320–430 and desktop centered 430px; scroll when needed. Use px/clamp rather than rpx which expands at tablet widths. Override inherited han-page backgrounds/pseudo elements locally. Consolidate existing duplicate scoped styles.

Bottom tabBar only 首页 and 我的 (registered routes unchanged). Create simple code-native Home/Profile icons as transparent 96px PNGs with a reproducible generator if necessary; selected teal #079777, inactive gray #989fa0. White bar, 13px labels, 27px icon, 66px height. 我的 remains existing upgrade placeholder.

Update focused homepage tests to new screenshot copy; retain reselect and exactly-two-entry assertions. Add asset/nav existence checks. Run focused owner-flow and visual-refresh tests. Report changed files and results without committing. Controller will handle browser screenshot validation and H5 build.

## Task 2: Asset and browser verification

Controller completes icon correction with built-in image generation. Save asset and prompt provenance. Build H5, inspect 320/390/430 and desktop, exercise document -> back -> questionnaire -> back -> document. Review scoped diff. Report visual limitations honestly; no claim of pixel identity or full-app redesign completion.
