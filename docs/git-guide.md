# Git 操作指南——零基础入门（只教你要用的，不教原理）

> **读者：** 钟睿宸、蔡子鑫
> **前提：** 电脑已安装 Git（命令行输入 `git --version` 有反应即可）
> **目的：** 把自己写的代码推到 GitHub，让陈家智能 Review

---

## 整个流程只用两步（记死了就行）

```
写代码 → 提交推送 → 陈家智审核
```

提交推送 = 四句命令（每句话是什么见下面）：

```
git add .
git commit -m "做了什么"
git pull origin dev
git push
```

下面逐句解释。

---

## 第一步：克隆仓库到本地（只做一次）

```bash
git clone https://github.com/chenjz111/HarmonyAI.git
cd HarmonyAI
```

## 第二步：切到自己的分支（只做一次）

钟睿宸：
```bash
git checkout feat/zhongrc
```

蔡子鑫：
```bash
git checkout feat/caizx
```

## 第三步：写代码

在你的项目文件夹里正常写代码、建文件。写完保存。

## 第四步：提交推送（每次写完一套功能就做一次）

打开 Git Bash，在项目文件夹路径下，**按顺序敲四句**：

### 第 1 句：打包
```bash
git add .
```
把这次写的所有文件打包到一起。`.` 表示"所有改动"。

### 第 2 句：写标签
```bash
git commit -m "做了什么——一句话描述"
```
例如：
```bash
git commit -m "feat: LangGraph demo 四步串行跑通，状态机正常"
```
```bash
git commit -m "feat: FastAPI 项目脚手架 + POST /api/assess 接口骨架"
```

### 第 3 句：拉最新（防止别人和你冲突）
```bash
git pull origin dev
```
把团队最新的代码拉下来，跟你自己的合并。万一提示 `CONFLICT`，截图发群里@陈家智，别自己乱操作。

### 第 4 句：推上去
```bash
git push
```
如果第一次推显示 `no upstream`，就用：
```bash
git push -u origin feat/zhongrc   # 钟睿宸
git push -u origin feat/caizx     # 蔡子鑫
```
以后再用就只用 `git push` 就行了。

## 第五步：到 GitHub 提 Pull Request

推完以后打开浏览器：
1. 进入 https://github.com/chenjz111/HarmonyAI
2. 页面上方会出现一个黄色的提示条 "feat/zhongrc had recent pushes" → 点 **Compare & pull request**
3. 确认左边 base 是 `dev`，右边 compare 是你的分支（如 `feat/zhongrc`）
4. 标题写清楚做了什么
5. 点 **Create pull request**
6. 以后每次推都会自动更新这个 PR

## 第六步：陈家智 Review 合入后，就完成了

如果 Review 提了修改意见，在你自己的分支上改了以后重复第四步（add → commit → push），PR 会自动更新，不用重新提。

---

## 两条铁律

1. **永远不要在自己分支做 `git push --force`**。如果推送失败了，先问陈家智。
2. **不知道当前在哪个分支，先敲：**
   ```bash
   git branch
   ```
   前面带 `*` 的就是当前分支。**绝对不要在 `dev` 或 `main` 分支上直接改代码。**

---

## 常见错误自查表

| 你想做什么 | 该敲什么 |
|-----------|---------|
| 提交所有改动并推送 | `git add .` → `git commit -m "..."` → `git push` |
| 看看自己改了什么 | `git status` |
| 看看提交记录 | `git log --oneline -5` |
| 写错 commit 信息了 | **别管，继续写代码**，下次 commit 写正确就行（初学者阶段不用改历史）|
| 推送失败提示"non-fast-forward" | 先 `git pull origin dev` 再 `git push` |
| 忘了自己在哪个分支 | `git branch` |

---

## 不会怎么办

截屏，发群里 @陈家智。不要自己搜 Stack Overflow 乱敲命令。

---

> 本文档是 Sprint 1 交付的一部分——环境就绪 = 有代码能推、能提 PR。不会推 = 不会交付 = Sprint 1 没完成。
