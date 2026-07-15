# Prompt Architecture（Prompt 架构）

> **版本：** V0.1（Draft，待 Kickoff Review）
> **日期：** 2026-07-15
> **作者：** 陈家智（Project Leader & AI Architect）
> **状态：** 等待团队 Review → V0.2 → Sprint 结束定 V1.0

---

## 文档定位

这份文档定义了 HarmonyAI 的 **Prompt 工程标准**——Prompt 怎么写、怎么组装、怎么版本化。

**核心原则：** 数据库不存完整 Prompt 字符串。存模板 + 参数，运行时由 Prompt Engine 组装。

**读者：**
- AI Engineering Lead（钟睿宸）：按此标准实现 Prompt Engine
- Medical Knowledge Engineer（nob）：理解 Prompt 参数来源，确保知识库可被参数化
- Backend Engineer（蔡子鑫）：理解 Prompt 存储方式（template_id + parameters，不存完整字符串）

---

## 第一章：Prompt 组成公式

### 1.1 Prompt 公式

```
Prompt = Role + Style + MusicTask + Instrument + Emotion + BPM + Ambient + Duration + Constraints
```

### 1.2 各模块说明

| 模块 | 含义 | 示例 | 必填 | 来源 |
|------|------|------|------|------|
| **Role** | 角色设定 | "你是一位中国传统音乐治疗专家" | ✅ | 固定模板 |
| **Style** | 音乐风格 | "五音疗法" / "中国传统民族音乐" | ✅ | 模板 + 参数 |
| **MusicTask** | 生成任务 | "请生成一段纯音乐" | ✅ | 固定模板 |
| **Instrument** | 乐器配置 | "古筝主旋律、竹笛副旋律、古琴和声" | ✅ | 处方Agent |
| **Emotion** | 情绪标签 | "舒缓、清新，如春风拂柳" | ✅ | 处方Agent |
| **BPM** | 节奏 | "BPM 68，节奏平稳舒缓" | ✅ | 处方Agent |
| **Ambient** | 环境音 | "背景加入自然流水声（音量15%）" | ⚠ | 处方Agent |
| **Duration** | 时长 | "生成15分钟" | ✅ | 处方Agent |
| **Constraints** | 约束条件 | "以五声音阶为主体、纯器乐无歌词" | ✅ | 固定模板 |

### 1.3 完整 Prompt 示例

```
[Role]
你是一位精通中国传统五音疗法的音乐治疗专家，擅长将中医理论转化为音乐参数。

[Style]
请生成一段中国传统民族风格的纯音乐，以五音疗法为理论基础。

[Instrument]
乐器配置：古筝（主旋律，70%）、竹笛（副旋律，20%）、古琴（和声背景，10%）。

[Emotion]
整体情绪：舒缓、清新，如春风拂柳。适合睡前放松。

[BPM]
节奏：BPM 68，平稳、舒缓，不急不缓。

[Ambient]
背景环境音：自然流水声（音量约15%），若有若无。

[Duration]
时长：15 分钟。

[Constraints]
重要约束：
- 以中国传统五声音阶（宫商角徵羽 = Do-Re-Mi-Sol-La）为主体旋律框架
- 可适当加入经过音、装饰音以增强音乐性
- 纯器乐，无人声/无歌词
- 整体保持中国民族音乐风格
- 避免激烈节奏和尖锐音色
- 主调为角调式（以 Mi 为主音），辅以宫调式（以 Do 为主音）
```

---

## 第二章：模板结构（Template Structure）

### 2.1 模板定义

每个模板是一个结构化对象，包含固定文本（template body）和参数占位符（parameters）。

```json
{
  "template_id": "CN_V1",
  "template_version": "1.0.0",
  "template_name": "Chinese Pentatonic Healing V1",
  "description": "中国五音疗愈音乐生成模板，Sprint 1 默认模板",
  "author": "陈家智",
  "created_at": "2026-07-15",

  "template_body": {
    "role": "你是一位精通中国传统五音疗法的音乐治疗专家，擅长将中医理论转化为音乐参数。",
    "style_prefix": "请生成一段中国传统民族风格的纯音乐，以五音疗法为理论基础。",
    "task": "请生成一段纯器乐音乐。",
    "constraints": [
      "以中国传统五声音阶（宫商角徵羽 = Do-Re-Mi-Sol-La）为主体旋律框架",
      "可适当加入经过音、装饰音以增强音乐性",
      "纯器乐，无人声/无歌词",
      "整体保持中国民族音乐风格",
      "避免激烈节奏和尖锐音色"
    ],
    "closing": "请直接生成音乐，不需要任何文字说明。"
  },

  "parameters": {
    "tone_weights": {
      "type": "array",
      "required": true,
      "description": "调式权重列表",
      "example": [
        { "tone_name": "角调式", "weight": 0.75, "role": "主调" },
        { "tone_name": "宫调式", "weight": 0.15, "role": "辅调" }
      ]
    },
    "bpm": {
      "type": "int",
      "required": true,
      "range": [40, 120],
      "description": "BPM 节奏",
      "example": 68
    },
    "duration_minutes": {
      "type": "int",
      "required": true,
      "options": [5, 10, 15, 20, 30],
      "description": "时长（分钟）",
      "example": 15
    },
    "instruments": {
      "type": "object",
      "required": true,
      "description": "乐器配置",
      "example": {
        "primary": { "name": "古筝", "weight": 0.70 },
        "secondary": { "name": "竹笛", "weight": 0.20 },
        "harmony": { "name": "古琴", "weight": 0.10 }
      }
    },
    "mood": {
      "type": "string",
      "required": true,
      "description": "情绪描述（中文自然语言）",
      "max_length": 100,
      "example": "舒缓、清新，如春风拂柳"
    },
    "scenario": {
      "type": "string",
      "required": true,
      "description": "使用场景",
      "options": ["睡前放松", "午后放松", "清晨唤醒", "专注冥想", "情绪释放"],
      "example": "睡前放松"
    },
    "ambient_sound": {
      "type": "object",
      "required": false,
      "description": "环境音配置",
      "example": { "name": "流水声", "volume": 0.15 }
    },
    "scale_constraint": {
      "type": "string",
      "required": true,
      "options": ["pentatonic_only", "pentatonic_primary", "hexatonic", "heptatonic"],
      "description": "音阶约束策略",
      "default": "pentatonic_primary",
      "example": "pentatonic_primary"
    },
    "language": {
      "type": "string",
      "required": false,
      "default": "zh-CN",
      "description": "Prompt 语言（未来国际化用）"
    }
  },

  "assembly_rules": {
    "order": ["role", "style_prefix", "task", "instruments_text", "emotion_text", "bpm_text", "ambient_text", "duration_text", "tone_constraint_text", "constraints_bullet", "closing"],
    "separator": "\n\n",
    "conditionals": {
      "ambient_text": "if parameters.ambient_sound exists"
    }
  }
}
```

### 2.2 模板与 Schema 的关系

```
③ 处方Agent 输出 → { template_id: "CN_V1", template_version: "1.0.0", parameters: {...} }
                          │
                          ▼
              Prompt Engine 查询模板 → 填充参数 → 组装 Prompt 字符串
                          │
                          ▼
              ④ 生成Agent 接收完整 Prompt 字符串 → 调 API
```

**关键分离原则：** Agent Schema 不存 Prompt 字符串，只存 `template_id` + `parameters`。这样换模板不影响 Agent 输出结构。

---

## 第三章：参数体系（Parameter System）

### 3.1 参数分类

```
Prompt 参数
├── 音乐核心参数（来自处方Agent ④→③）
│   ├── tone_weights:     调式权重
│   ├── bpm:              BPM
│   ├── duration_minutes: 时长
│   └── instruments:      乐器配置
│
├── 音乐风格参数（来自规则引擎）
│   ├── mood:             情绪描述
│   ├── scenario:         使用场景
│   ├── ambient_sound:    环境音
│   └── scale_constraint: 音阶约束
│
└── 系统参数（固定/配置）
    ├── language:          语言
    └── template_id:       模板标识
```

### 3.2 参数验证规则

```python
# Prompt Engine 组装前验证
PARAM_VALIDATION = {
    "bpm": {
        "type": int,
        "range": [40, 120],
        "error": "BPM 必须在 40-120 之间"
    },
    "duration_minutes": {
        "type": int,
        "options": [5, 10, 15, 20, 30],
        "error": "时长必须是 5/10/15/20/30 分钟之一"
    },
    "tone_weights": {
        "type": list,
        "sum_must_equal": 1.0,
        "error": "调式权重之和必须等于 1.0"
    },
    "instruments": {
        "type": object,
        "min_instruments": 1,
        "max_instruments": 5,
        "error": "乐器数量必须在 1-5 之间"
    },
    "mood": {
        "type": str,
        "max_length": 100,
        "error": "情绪描述不能超过 100 字"
    }
}
```

### 3.3 参数默认值（Fallback）

当某个参数缺失或异常时，使用默认值：

| 参数 | 默认值 | 触发条件 |
|------|--------|----------|
| `bpm` | 68 | BPM 超出 40-120 范围 |
| `duration_minutes` | 10 | 时长不在允许列表中 |
| `tone_weights` | 角调 1.0 | 权重之和 ≠ 1.0 |
| `instruments` | 古筝 solo | 乐器列表为空 |
| `mood` | "平和、舒缓" | mood 为空 |
| `scale_constraint` | "pentatonic_primary" | 未指定 |
| `ambient_sound` | null（无环境音） | 未指定 |

---

## 第四章：组装规则（Assembly Rules）

### 4.1 组装流程

```python
class PromptEngine:
    """
    Prompt 组装引擎。
    
    输入：template_id + parameters
    输出：完整 Prompt 字符串（直接喂给音乐生成 API）
    """
    
    def assemble(self, template_id: str, parameters: dict) -> str:
        # Step 1: 查询模板
        template = self.template_store.get(template_id)
        if not template:
            raise TemplateNotFoundError(f"模板 {template_id} 不存在")
        
        # Step 2: 验证参数
        self.validate_params(parameters, template["parameters"])
        
        # Step 3: 构建各部分文本
        sections = []
        
        # Role（固定）
        sections.append(template["template_body"]["role"])
        
        # Style（固定）
        sections.append(template["template_body"]["style_prefix"])
        
        # Task（固定）
        sections.append(template["template_body"]["task"])
        
        # Instruments（动态）
        instr_text = self._build_instrument_text(parameters["instruments"])
        sections.append(instr_text)
        
        # Emotion（动态）
        emotion_text = f"整体情绪：{parameters['mood']}。适合{parameters['scenario']}。"
        sections.append(emotion_text)
        
        # BPM（动态）
        bpm_text = f"节奏：BPM {parameters['bpm']}，平稳、舒缓。"
        sections.append(bpm_text)
        
        # Ambient（条件渲染）
        if parameters.get("ambient_sound"):
            amb = parameters["ambient_sound"]
            amb_text = f"背景环境音：自然{amb['name']}（音量约{int(amb['volume']*100)}%），若有若无。"
            sections.append(amb_text)
        
        # Duration（动态）
        dur_text = f"时长：{parameters['duration_minutes']} 分钟。"
        sections.append(dur_text)
        
        # Tone constraint（动态）
        tone_text = self._build_tone_constraint(parameters["tone_weights"])
        sections.append(tone_text)
        
        # Constraints（固定 + 动态）
        constraints = template["template_body"]["constraints"].copy()
        constraints.append(self._build_scale_constraint(parameters.get("scale_constraint", "pentatonic_primary")))
        constraints_text = "重要约束：\n" + "\n".join(f"- {c}" for c in constraints)
        sections.append(constraints_text)
        
        # Closing（固定）
        sections.append(template["template_body"]["closing"])
        
        # Step 4: 组装
        separator = template["assembly_rules"]["separator"]
        return separator.join(sections)
    
    def _build_instrument_text(self, instruments: dict) -> str:
        parts = []
        if instruments.get("primary"):
            parts.append(f"{instruments['primary']['name']}（主旋律，{int(instruments['primary']['weight']*100)}%）")
        if instruments.get("secondary"):
            parts.append(f"{instruments['secondary']['name']}（副旋律，{int(instruments['secondary']['weight']*100)}%）")
        if instruments.get("harmony"):
            parts.append(f"{instruments['harmony']['name']}（和声背景，{int(instruments['harmony']['weight']*100)}%）")
        return "乐器配置：" + "、".join(parts) + "。"
    
    def _build_tone_constraint(self, tone_weights: list) -> str:
        primary = [t for t in tone_weights if t.get("role") == "主调"]
        secondary = [t for t in tone_weights if t.get("role") != "主调"]
        
        text = f"主调为{primary[0]['tone_name']}（以 {self._tone_to_note(primary[0]['tone_name'])} 为主音）"
        if secondary:
            sec_names = "、".join(f"{t['tone_name']}（以 {self._tone_to_note(t['tone_name'])} 为主音）" for t in secondary)
            text += f"，辅以{sec_names}"
        text += "。"
        return text
    
    def _build_scale_constraint(self, constraint: str) -> str:
        mapping = {
            "pentatonic_only": "严格使用五声音阶（宫商角徵羽），不使用任何偏音",
            "pentatonic_primary": "以五声音阶为主体，可适当加入经过音和装饰音",
            "hexatonic": "使用六声调式，加入变宫(Si)或清角(Fa)作为色彩音",
            "heptatonic": "使用七声调式，允许完整七声音阶"
        }
        return mapping.get(constraint, mapping["pentatonic_primary"])
    
    def _tone_to_note(self, tone_name: str) -> str:
        mapping = {"角调式": "Mi", "徵调式": "Sol", "宫调式": "Do", "商调式": "Re", "羽调式": "La"}
        return mapping.get(tone_name, "Do")
```

### 4.2 组装后的 Prompt 检查清单

组装完成后，Prompt Engine 自动检查：

- [ ] 总字符数 ≤ 2000（防止 API 截断）
- [ ] 包含所有必填模块（Role/Style/Instrument/Emotion/BPM/Duration/Constraints）
- [ ] 没有负面禁止语句（如"禁止 Fa 和 Si"）——改用正向约束
- [ ] 没有英文单词（除 BPM）——音乐生成 API 对中文理解更好
- [ ] 语气为正向指导（"应该…"），非负向禁止（"不要…"）

---

## 第五章：模板版本化规范

### 5.1 版本号规则（语义化版本）

```
MAJOR.MINOR.PATCH
  │     │     └── PATCH: 措辞微调、标点修正（不影响输出）
  │     └─────── MINOR: 新增参数、调整某个模块的表述（输出可能有变化）
  └───────────── MAJOR: 模板结构大改、参数体系重构（输出显著变化）
```

### 5.2 模板变更流程

```
1. 在 prompt/ 目录下创建新版本文件
   例如：prompt/v1/CN_V1.0.0.json → prompt/v1/CN_V1.1.0.json

2. 更新 CHANGELOG（prompt/CHANGELOG.md）

3. 通知受影响方：
   - 钟睿宸（AI）：Prompt Engine 适配
   - nob（Medical）：参数语义是否变化
   - 蔡子鑫（Backend）：数据库 template 表是否需要新记录

4. 旧模板保留 2 个 Sprint 后废弃
```

### 5.3 模板存储结构

```
prompt/
├── CHANGELOG.md              ← 模板变更日志
├── v1/
│   ├── CN_V1.0.0.json        ← 中国五音疗愈模板（默认）
│   ├── CN_V1.0.0.md          ← 人类可读版本
│   └── CN_V1.0.0_example.txt ← 组装后的 Prompt 示例
└── deprecated/               ← 废弃模板存档
```

---

## 第六章：Sprint 1 模板清单

Sprint 1 只需一个模板。后续 Sprint 可扩展。

| 模板 ID | 名称 | 用途 | 状态 |
|---------|------|------|------|
| CN_V1 | Chinese Pentatonic Healing V1 | 默认五音疗愈音乐生成 | Sprint 1 使用 |
| CN_V2 | — | 带个性化偏好的版本 | Sprint 2+ |
| EN_V1 | — | 英文版（国际化） | 远期 |

---

## 附录 A：文档版本历史

| 版本 | 日期 | 变更 | 作者 |
|------|------|------|------|
| V0.1 | 2026-07-15 | 初始草稿，六章完整 | 陈家智 |
| V0.2 | — | Kickoff Review 后修订 | 陈家智 |
| V1.0 | — | Sprint 1 结束定稿 | 陈家智 |

## 附录 B：给各角色的阅读指引

| 角色 | 重点阅读 | 可跳过 |
|------|----------|--------|
| AI Engineering Lead | 全文（这是你的核心施工图） | — |
| Medical Knowledge Engineer | 第3章（参数来源） | 第4章（组装代码） |
| Backend Engineer | 第1、2、5章（存储 + 版本化） | 第4章（组装代码） |
| Client Engineer | 第1章（理解 Prompt 长什么样） | 第4、5章 |
