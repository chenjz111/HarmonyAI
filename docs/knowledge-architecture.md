# Knowledge Architecture（知识架构）

> **版本：** V0.1（Draft，待 Kickoff Review）
> **日期：** 2026-07-15
> **作者：** 陈家智（Project Leader & AI Architect）
> **状态：** 等待团队 Review → V0.2 → Sprint 结束定 V1.0

---

## 文档定位

这份文档定义了 HarmonyAI 的**知识流动规则**——数据如何从"用户输入"一步步变成"音乐参数"。

**读者：**
- Medical Knowledge Engineer（nob）：按此标准填充知识库和映射 JSON
- AI Engineering Lead（钟睿宸）：按此标准实现 Prompt Engine 和 RAG 检索
- Backend Engineer（蔡子鑫）：按此标准设计数据库 ER 图
- Client Engineer（彭翔）：按此标准理解数据流，设计 UI 交互

**核心原则：** 所有 AI 推理必须基于 Knowledge Engine，不凭空生成。每一步映射都有文献出处。

---

## 第一章：整体知识流（Knowledge Flow）

### 1.1 一句话

> 用户的情绪体验 → 中医证型 → 五行归属 → 五音调式 → 音乐特征参数 → Prompt 标签 → 音乐生成 Prompt

### 1.2 完整映射链（6 步）

```
Step 1          Step 2           Step 3          Step 4           Step 5            Step 6
 Emotion   →    Syndrome    →    Wuxing     →    Tone       →    Music Feature →   Prompt Tag
（情绪）       （中医证型）       （五行/脏腑）     （五音调式）       （音乐参数）        （Prompt 标签）
                                                                                   
 焦虑       →    肝郁化火    →    木 / 肝     →    角调 (Mi)  →    古筝            calm
                                                                           68 BPM          healing
 抑郁       →    肝气郁结    →    木 / 肝     →    角调 (Mi)  →    森林环境        guqin
                                                                           竹笛            soothing
 愤怒       →    肝阳上亢    →    木 / 肝     →    角调 (Mi)  →    65-75 BPM      traditional
                                                                           ...             ...
 过度思考   →    心脾两虚    →    火+土/心+脾 →    徵调+宫调   →    琵琶+古琴      peaceful
                                                                           70 BPM          focus
 ...       →    ...        →    ...         →    ...        →    ...           ...
```

### 1.3 每一层的职责

| 步骤 | 层名 | 输入 | 输出 | 谁负责 | 谁实现 |
|------|------|------|------|--------|--------|
| 1 | Emotion | 用户问卷/病例 | 情绪五维分数 | ① 评估Agent | Backend + AI |
| 2 | Syndrome | 情绪五维分数 | 中医证型 + 可信度 | ② 辨证Agent | AI (LangGraph) |
| 3 | Wuxing | 证型 | 五行 + 脏腑 | ② 辨证Agent | AI (规则引擎) |
| 4 | Tone | 五行 + 脏腑 | 主调 + 辅调 + 权重 | ③ 处方Agent | AI (权重网络) |
| 5 | Music Feature | 调式 + 权重 | BPM/乐器/环境音/情绪标签 | ③ 处方Agent | AI (知识库检索) |
| 6 | Prompt Tag | Music Feature | 组装后的 Prompt 标签 | ③ 处方Agent | AI (Prompt Engine) |

### 1.4 为什么是链式而非跳步

```
❌ 错误做法：
  用户说"焦虑" → AI 直接生成音乐
  问题：不可解释、不可追溯、不可优化

✅ 正确做法：
  用户说"焦虑" → 辨证→五行→调式→BPM→乐器→Prompt→音乐
  好处：每一步可独立调试、可引用文献、可替换模型
```

---

## 第二章：每一层的数据结构

### 2.1 Emotion（情绪层）

**数据来源：** 问卷自评（30 题 Likert 5 级）+ 病例 OCR

```json
{
  "emotion_profile": {
    "anxiety": { "score": 82, "label": "焦虑", "severity": "high" },
    "depression": { "score": 35, "label": "抑郁", "severity": "low" },
    "anger": { "score": 60, "label": "愤怒", "severity": "medium" },
    "fear": { "score": 20, "label": "恐惧", "severity": "low" },
    "overthinking": { "score": 45, "label": "过度思考", "severity": "medium" }
  },
  "dominant_emotion": "anxiety",
  "dominant_score": 82
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `emotion_profile.{key}.score` | int (0-100) | ✅ | 情绪强度分数 |
| `emotion_profile.{key}.label` | string | ✅ | 中文标签 |
| `emotion_profile.{key}.severity` | enum | ✅ | low / medium / high |
| `dominant_emotion` | string | ✅ | 最高分情绪 key |
| `dominant_score` | int | ✅ | 最高分数值 |

**五维度设计依据：** 参考中医七情（怒喜思悲恐惊忧）归并为五维，与五行一一对应。

---

### 2.2 Syndrome（证型层）

**数据来源：** 规则引擎（硬编码映射表）+ LLM（Qwen2.5-7B）+ RAG 知识库

```json
{
  "syndrome_diagnosis": {
    "primary": {
      "syndrome_id": "syd_001",
      "name": "肝郁化火",
      "element": "木",
      "organ": "肝",
      "emotion": "怒",
      "severity_level": 3,
      "severity_name": "中度"
    },
    "secondary": [
      {
        "syndrome_id": "syd_018",
        "name": "阴虚",
        "element": "水",
        "organ": "肾",
        "emotion": "恐",
        "severity_level": 2,
        "severity_name": "轻度"
      }
    ]
  }
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `syndrome_id` | string | ✅ | 证型唯一标识，如 `syd_001` |
| `name` | string | ✅ | 中文证型名 |
| `element` | string | ✅ | 五行：木/火/土/金/水 |
| `organ` | string | ✅ | 对应脏腑 |
| `emotion` | string | ✅ | 关联情志 |
| `severity_level` | int (1-5) | ✅ | 严重程度（数字给 AI） |
| `severity_name` | string | ✅ | 严重程度名称（文字给前端） |

**Sprint 1 证型范围（MVP）：** 仅覆盖 8 个高频证型

| syndrome_id | 证型名 | 五行 | 脏腑 | 常见情绪 |
|-------------|--------|------|------|----------|
| syd_001 | 肝郁化火 | 木 | 肝 | 焦虑、烦躁 |
| syd_002 | 肝气郁结 | 木 | 肝 | 抑郁、闷闷不乐 |
| syd_003 | 心火上炎 | 火 | 心 | 烦躁、失眠 |
| syd_004 | 心脾两虚 | 火+土 | 心+脾 | 过度思考、健忘 |
| syd_005 | 脾虚湿困 | 土 | 脾 | 思虑、疲倦 |
| syd_006 | 肺气虚 | 金 | 肺 | 悲伤、气短 |
| syd_007 | 肾阴不足 | 水 | 肾 | 恐惧、腰酸 |
| syd_008 | 心肾不交 | 火+水 | 心+肾 | 失眠、心悸 |

---

### 2.3 Wuxing（五行层）

**数据来源：** 规则引擎（硬编码，不受 LLM 幻觉影响）

```json
{
  "wuxing_mapping": {
    "primary": {
      "element": "木",
      "organ": "肝",
      "emotion": "怒",
      "tone": "角",
      "note": "Mi",
      "direction": "东",
      "season": "春"
    },
    "relationships": {
      "generates": "火",
      "generated_by": "水",
      "restricts": "土",
      "restricted_by": "金"
    }
  }
}
```

**五行→五音硬编码映射表（不可改，除非有新文献推翻）：**

| 五行 | 脏腑 | 五音 | 西方音名 | 情志 | 方向 | 季节 |
|------|------|------|----------|------|------|------|
| 木 | 肝 | 角 (Jué) | E (Mi) | 怒 | 东 | 春 |
| 火 | 心 | 徵 (Zhǐ) | G (Sol) | 喜 | 南 | 夏 |
| 土 | 脾 | 宫 (Gōng) | C (Do) | 思 | 中 | 长夏 |
| 金 | 肺 | 商 (Shāng) | D (Re) | 悲 | 西 | 秋 |
| 水 | 肾 | 羽 (Yǔ) | A (La) | 恐 | 北 | 冬 |

> **文献依据：**《黄帝内经·素问·阴阳应象大论》——"东方生风，风生木……在脏为肝……在音为角"

---

### 2.4 Tone（五音调式层）

**数据来源：** 权重网络计算（规则引擎 + 生克选调算法）

```json
{
  "tone_assignment": {
    "primary_tone": {
      "tone_id": "jiao",
      "tone_name": "角调",
      "note": "Mi",
      "element": "木",
      "organ": "肝",
      "weight": 0.75,
      "role": "主调"
    },
    "secondary_tones": [
      {
        "tone_id": "gong",
        "tone_name": "宫调",
        "note": "Do",
        "element": "土",
        "organ": "脾",
        "weight": 0.15,
        "role": "辅调",
        "strategy": "木克土，用宫调护脾胃，防肝病传脾"
      },
      {
        "tone_id": "yu",
        "tone_name": "羽调",
        "note": "La",
        "element": "水",
        "organ": "肾",
        "weight": 0.10,
        "role": "辅调",
        "strategy": "水生木，羽调滋水涵木"
      }
    ]
  }
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `tone_id` | string | ✅ | 调式唯一标识：jiao/zhi/gong/shang/yu |
| `tone_name` | string | ✅ | 中文名称 |
| `note` | string | ✅ | 西方音名 |
| `weight` | float (0-1) | ✅ | 权重，所有权重之和 = 1.0 |
| `role` | enum | ✅ | 主调 / 辅调 / 克调 |
| `strategy` | string | ✅ | 选调策略说明（生克乘侮逻辑） |

**Sprint 1 权重矩阵（初始值，后期可被反馈数据优化）：**

| 证型 | 角(Mi/木) | 徵(Sol/火) | 宫(Do/土) | 商(Re/金) | 羽(La/水) |
|------|-----------|------------|-----------|-----------|-----------|
| 肝郁化火 | **0.75** | 0.05 | 0.15 | 0.00 | 0.05 |
| 肝气郁结 | **0.70** | 0.05 | 0.15 | 0.00 | 0.10 |
| 心火上炎 | 0.10 | **0.60** | 0.05 | 0.00 | 0.25 |
| 心脾两虚 | 0.15 | **0.50** | **0.30** | 0.00 | 0.05 |
| 脾虚湿困 | 0.15 | 0.05 | **0.70** | 0.00 | 0.10 |
| 肺气虚 | 0.00 | 0.05 | 0.10 | **0.75** | 0.10 |
| 肾阴不足 | 0.05 | 0.00 | 0.05 | 0.10 | **0.80** |
| 心肾不交 | 0.05 | **0.45** | 0.05 | 0.00 | **0.45** |

---

### 2.5 Music Feature（音乐特征层）

**数据来源：** 知识库检索 + 规则表

```json
{
  "music_feature": {
    "bpm": 68,
    "bpm_range": { "min": 65, "max": 75 },
    "duration_minutes": 15,
    "instruments": [
      { "id": "guzheng", "name": "古筝", "role": "primary", "weight": 0.70 },
      { "id": "zhudi", "name": "竹笛", "role": "secondary", "weight": 0.20 },
      { "id": "guqin", "name": "古琴", "role": "harmony", "weight": 0.10 }
    ],
    "ambient_sound": { "id": "water_stream", "name": "流水声", "volume": 0.15 },
    "mood": "舒缓、清新，如春风拂柳",
    "scenario": "睡前放松",
    "scale_constraint": "pentatonic_primary"
  }
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `bpm` | int | ✅ | 精确 BPM |
| `bpm_range` | object | ✅ | BPM 可选区间 |
| `duration_minutes` | int | ✅ | 单曲时长（5/10/15/20/30） |
| `instruments` | array | ✅ | 乐器组合，带角色和权重 |
| `ambient_sound` | object | ⚠ | 环境音，可选 |
| `mood` | string | ✅ | 情绪描述（中文，给 Prompt 用） |
| `scenario` | string | ✅ | 使用场景 |
| `scale_constraint` | enum | ✅ | pentatonic_primary / pentatonic_only / hexatonic / heptatonic |

**BPM 参考范围（按调式和证候严重程度）：**

| 调式 | 轻度 (1-2) | 中度 (3) | 重度 (4-5) |
|------|-----------|----------|-----------|
| 角调 | 70-78 | 65-75 | 55-65 |
| 徵调 | 72-80 | 68-76 | 60-68 |
| 宫调 | 62-70 | 58-66 | 52-60 |
| 商调 | 70-78 | 66-74 | 58-66 |
| 羽调 | 58-66 | 52-62 | 48-56 |

**乐器库（Sprint 1 范围）：**

| 乐器 ID | 名称 | 类别 | 五行关联 | 典型调式 |
|---------|------|------|----------|----------|
| guzheng | 古筝 | 弹拨 | 木 | 角调 |
| guqin | 古琴 | 弹拨 | 木/水 | 角调/羽调 |
| zhudi | 竹笛 | 吹管 | 木 | 角调 |
| xiao | 箫 | 吹管 | 水 | 羽调 |
| pipa | 琵琶 | 弹拨 | 火 | 徵调 |
| erhu | 二胡 | 拉弦 | 金 | 商调 |
| bianzhong | 编钟 | 打击 | 土 | 宫调 |
| sheng | 笙 | 吹管 | 土 | 宫调 |
| xun | 埙 | 吹管 | 土/金 | 宫调/商调 |

**环境音库（Sprint 1 范围）：**

| 环境音 ID | 名称 | 适用场景 | 适用情绪 |
|-----------|------|----------|----------|
| water_stream | 流水声 | 睡前放松 | 焦虑、烦躁 |
| forest | 森林鸟鸣 | 午后放松 | 抑郁、疲倦 |
| rain | 雨声 | 冥想、专注 | 过度思考 |
| wind_bamboo | 风吹竹林 | 清晨 | 各种 |
| ocean_wave | 海浪 | 深度放松 | 失眠、紧张 |
| bonfire | 篝火 | 晚间放松 | 恐惧、孤独 |

---

### 2.6 Prompt Tag（Prompt 标签层）

**数据来源：** Prompt Engine 从 Music Feature 自动提取 + 组装

```json
{
  "prompt_tags": {
    "role": "traditional_chinese_music_therapist",
    "style": ["pentatonic", "traditional_chinese", "healing"],
    "emotion_tags": ["calm", "soothing", "gentle"],
    "instrument_tags": ["guzheng", "zhudi", "guqin"],
    "tempo_tag": "slow",
    "ambient_tag": "water_stream",
    "scenario_tag": "bedtime_relaxation",
    "duration_tag": "15_minutes",
    "constraint_tags": ["pentatonic_primary", "no_lyrics", "pure_instrumental"]
  }
}
```

---

## 第三章：Mapping 规则

### 3.1 为什么不是一对一

**核心观点：** 中医五音疗法不是"焦虑 = 角调"的简单查表，而是基于**五行生克乘侮**的多维映射。

```
一个情绪 ──→ 多个证型（同是焦虑，可能是肝郁化火、心肾不交、或阴虚火旺）
     │
     ▼
一个证型 ──→ 多个五行（肝郁化火涉及木+火，心脾两虚涉及火+土）
     │
     ▼
一个五行 ──→ 多个调式策略（主角调 + 辅调 + 克调，基于生克关系）
     │
     ▼
一个调式 ──→ 多个音乐特征（不同BPM区间、不同乐器组合、不同环境音）
```

### 3.2 生克选调规则

```
五行相生：木→火→土→金→水→木
五行相克：木→土→水→火→金→木

选调逻辑：
1. 主调 = 证型对应的本脏之音（如肝=角调）
2. 辅调1 = 我克之脏的音（如木克土→宫调，防传变）     ← "既病防变"
3. 辅调2 = 生我之脏的音（如水生木→羽调，虚则补其母）  ← "虚则补其母"
4. 权重之和 = 1.0
```

### 3.3 证型→权重映射伪代码

```python
def compute_tone_weights(syndrome_id: str, severity: int) -> dict:
    """
    输入：证型ID + 严重程度
    输出：{角: 0.75, 宫: 0.15, 羽: 0.10}
    """
    base_weights = WEIGHT_MATRIX[syndrome_id]  # 查硬编码表
    
    # 严重程度调整：越重，主调权重越高
    if severity >= 4:
        base_weights[primary_tone] += 0.05
        # 从辅调中均摊扣除
        for tone in secondary_tones:
            base_weights[tone] -= 0.025
    
    # 归一化
    total = sum(base_weights.values())
    return {k: round(v/total, 2) for k, v in base_weights.items()}
```

### 3.4 乐器选择规则

```python
def select_instruments(primary_tone: str, bpm: int) -> list:
    """
    输入：主调式 + BPM
    输出：[{古筝, primary, 0.70}, {竹笛, secondary, 0.20}, {古琴, harmony, 0.10}]
    
    规则优先级：
    1. 首选与调式五行相同的乐器（角调→古筝/竹笛）
    2. 辅乐器选生我或我生的五行乐器
    3. BPM < 60 偏好低音乐器（古琴/箫/埙）
    4. BPM > 75 偏好明亮乐器（竹笛/琵琶）
    """
```

---

## 第四章：可信度体系（Confidence）

### 4.1 可信度级别

| 星级 | 级别 | 含义 | 来源 | 映射权重 |
|------|------|------|------|----------|
| ★★★★★ | Level A | 最高可信度 | RCT 随机对照试验、Meta分析 | 1.0 |
| ★★★★ | Level B | 高可信度 | 经典文献（《黄帝内经》等） | 0.85 |
| ★★★ | Level C | 中可信度 | 专家共识、临床经验总结 | 0.65 |
| ★★ | Level D | 参考级 | 个案报告、经验总结 | 0.45 |
| ★ | Level E | 数据级 | 用户反馈数据统计 | 随样本量增长 |

### 4.2 可信度传播规则

```
知识流中每一步的可信度向下传播并衰减：

Agent ① confidence = OCR准确率 × 术语映射命中率
Agent ② confidence = 规则引擎(0.85) × LLM(0.72) × 文献支持度(0.65)
Agent ③ confidence = Agent② confidence × 知识库匹配度 × 权重网络覆盖率
Agent ④ confidence = API调用成功率（技术指标，非医学）
Agent ⑤ confidence = 用户反馈一致性

任一环节 confidence < 0.40 → 触发就医提醒
```

### 4.3 Medical Knowledge Engineer 的工作标准

nob 在整理知识库时，**每条知识必须标注：**

```json
{
  "knowledge_id": "k_001",
  "content": "角调音乐对肝郁化火证焦虑患者有效率82.3%",
  "source_type": "RCT",
  "source_title": "五音疗法对肝郁化火型焦虑障碍的临床观察",
  "source_author": "Zhang et al.",
  "source_year": 2023,
  "source_journal": "中医杂志",
  "credibility_level": "A",
  "credibility_score": 0.95,
  "applicable_syndromes": ["syd_001"],
  "applicable_emotions": ["anxiety"],
  "tags": ["角调", "肝郁化火", "焦虑", "古筝"]
}
```

---

## 第五章：完整 JSON 示例

### 5.1 最小完整映射示例

**输入（用户场景）：** 用户报告焦虑、失眠、心悸

**输出（完整知识映射链）：**

```json
{
  "session_id": "sess_20260715_001",
  "user_id": "u_001",

  "step1_emotion": {
    "anxiety": 82,
    "depression": 35,
    "anger": 60,
    "fear": 20,
    "overthinking": 45,
    "dominant": "anxiety"
  },

  "step2_syndrome": {
    "primary": { "id": "syd_001", "name": "肝郁化火", "element": "木", "organ": "肝" },
    "secondary": [{ "id": "syd_008", "name": "心肾不交", "element": "火+水", "organ": "心+肾" }],
    "confidence": 0.71
  },

  "step3_wuxing": {
    "primary": { "element": "木", "organ": "肝", "emotion": "怒" },
    "sheng_ke": { "generates": "火", "restricts": "土" }
  },

  "step4_tone": {
    "primary": { "tone": "角", "note": "Mi", "weight": 0.75, "role": "主调" },
    "secondary": [
      { "tone": "宫", "note": "Do", "weight": 0.15, "role": "辅调", "reason": "木克土，护脾胃" },
      { "tone": "羽", "note": "La", "weight": 0.10, "role": "辅调", "reason": "水生木，滋水涵木" }
    ]
  },

  "step5_music_feature": {
    "bpm": 68,
    "duration_minutes": 15,
    "instruments": [
      { "id": "guzheng", "name": "古筝", "role": "primary", "weight": 0.70 },
      { "id": "zhudi", "name": "竹笛", "role": "secondary", "weight": 0.20 },
      { "id": "guqin", "name": "古琴", "role": "harmony", "weight": 0.10 }
    ],
    "ambient_sound": { "id": "water_stream", "name": "流水声", "volume": 0.15 },
    "mood": "舒缓、清新，如春风拂柳",
    "scenario": "睡前放松"
  },

  "step6_prompt_tags": {
    "style": ["pentatonic", "traditional_chinese", "healing"],
    "emotion": ["calm", "soothing", "gentle"],
    "instruments": ["guzheng", "zhudi", "guqin"],
    "tempo": "slow_68bpm",
    "ambient": "water_stream",
    "scenario": "bedtime"
  },

  "evidence_chain": [
    {
      "step": "emotion→syndrome",
      "source": "规则引擎 SRE_v1.0",
      "confidence": 0.85,
      "reason": "焦虑82分→怒→木→肝，规则命中"
    },
    {
      "step": "syndrome→tone",
      "source": "《黄帝内经·素问·阴阳应象大论》",
      "confidence": 0.95,
      "reason": "肝属木，在音为角"
    },
    {
      "step": "tone→instrument",
      "source": "专家经验库 EXP_v1.0",
      "confidence": 0.65,
      "reason": "古筝为角调首选乐器（3/3位专家一致）"
    },
    {
      "step": "tone→bpm",
      "source": "RCT_2023_Zhang",
      "confidence": 0.85,
      "reason": "角调65-75BPM区间，中度取68"
    }
  ],

  "overall_confidence": 0.71,
  "warning_level": "info",
  "warning_message": "本系统评估可信度71%，仅供参考。如有持续不适，建议咨询专业中医师。"
}
```

---

## 附录 A：文档版本历史

| 版本 | 日期 | 变更 | 作者 |
|------|------|------|------|
| V0.1 | 2026-07-15 | 初始草稿，五章完整 | 陈家智 |
| V0.2 | — | Kickoff Review 后修订 | 陈家智 |
| V1.0 | — | Sprint 1 结束定稿 | 陈家智 |

## 附录 B：给各角色的阅读指引

| 角色 | 重点阅读 | 可跳过 |
|------|----------|--------|
| Medical Knowledge Engineer | 第1、2、4章（知识流 + 数据结构 + 可信度） | 第3章（AI 实现） |
| AI Engineering Lead | 全文 | — |
| Backend Engineer | 第2章（数据结构 → ER 图设计） | 第3、4章 |
| Client Engineer | 第1章（数据流 → 理解 UI 交互链路） | 第3、4章 |
