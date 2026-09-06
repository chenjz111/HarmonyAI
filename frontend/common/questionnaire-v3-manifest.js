/**
 * 五脏状态问卷 V3.0.1 权威清单（冻结版本）
 * 来源：knowledge/v3/questionnaire-v3.0.1.json（单一事实来源，前端逐字同步）
 * - Issue #111 / V3.1_FREEZE_BASELINE 83fe2f4：Questionnaire 3.0.1 是唯一可执行问卷
 * - content_checksum = sha256:69a01d07…（与 backend flow_v31.py / knowledge manifest 一致）
 * - q01-q05 为频率题（frequency_0_4，每题含 5 个个性化选项文案）
 * - q06-q10 为多选题（multi_choice_evidence，含互斥的"都很少出现"选项）
 * - user_goal 为疗愈诉求选填配置（7 code，max_selections=2，custom_goal_text ≤200 字）
 * 注意：题目与选项文案属于医学审核冻结内容，任何人不得在前端擅自增删改
 */

export const QUESTIONNAIRE_MANIFEST = {
  "schema_id": "questionnaire_v3",
  "schema_version": "3.0.1",
  "manifest_version": "medical_v3.0.1",
  "time_window": "past_7_days",
  "time_window_days": 7,
  "question_count": 10,
  "questions": [
    {
      "question_id": "q01",
      "position": 1,
      "prompt": "最近一周，你会不会比较容易着急、烦躁？",
      "answer_type": "frequency_0_4",
      "required": true,
      "min_selections": null,
      "max_selections": null,
      "options": [
        {
          "option_code": "0",
          "label": "平静如水",
          "score": 0,
          "claim_code": "anger_tendency",
          "is_none": false,
          "exclusive_with": [],
          "evidence_semantic_ref": "claim-dictionary-v3.0.json#anger_tendency"
        },
        {
          "option_code": "1",
          "label": "偶尔有一丝火气",
          "score": 1,
          "claim_code": "anger_tendency",
          "is_none": false,
          "exclusive_with": [],
          "evidence_semantic_ref": "claim-dictionary-v3.0.json#anger_tendency"
        },
        {
          "option_code": "2",
          "label": "像温水在翻滚",
          "score": 2,
          "claim_code": "anger_tendency",
          "is_none": false,
          "exclusive_with": [],
          "evidence_semantic_ref": "claim-dictionary-v3.0.json#anger_tendency"
        },
        {
          "option_code": "3",
          "label": "像是个火药桶",
          "score": 3,
          "claim_code": "anger_tendency",
          "is_none": false,
          "exclusive_with": [],
          "evidence_semantic_ref": "claim-dictionary-v3.0.json#anger_tendency"
        },
        {
          "option_code": "4",
          "label": "已经快爆发了",
          "score": 4,
          "claim_code": "anger_tendency",
          "is_none": false,
          "exclusive_with": [],
          "evidence_semantic_ref": "claim-dictionary-v3.0.json#anger_tendency"
        }
      ],
      "evidence_semantic_ref": "claim-dictionary-v3.0.json#anger_tendency"
    },
    {
      "question_id": "q02",
      "position": 2,
      "prompt": "最近一周，你会不会觉得心里静不下来、容易兴奋或紧张？",
      "answer_type": "frequency_0_4",
      "required": true,
      "min_selections": null,
      "max_selections": null,
      "options": [
        {
          "option_code": "0",
          "label": "心如止水",
          "score": 0,
          "claim_code": "agitation_tendency",
          "is_none": false,
          "exclusive_with": [],
          "evidence_semantic_ref": "claim-dictionary-v3.0.json#agitation_tendency"
        },
        {
          "option_code": "1",
          "label": "偶尔有点小涟漪",
          "score": 1,
          "claim_code": "agitation_tendency",
          "is_none": false,
          "exclusive_with": [],
          "evidence_semantic_ref": "claim-dictionary-v3.0.json#agitation_tendency"
        },
        {
          "option_code": "2",
          "label": "心里七上八下",
          "score": 2,
          "claim_code": "agitation_tendency",
          "is_none": false,
          "exclusive_with": [],
          "evidence_semantic_ref": "claim-dictionary-v3.0.json#agitation_tendency"
        },
        {
          "option_code": "3",
          "label": "坐立难安",
          "score": 3,
          "claim_code": "agitation_tendency",
          "is_none": false,
          "exclusive_with": [],
          "evidence_semantic_ref": "claim-dictionary-v3.0.json#agitation_tendency"
        },
        {
          "option_code": "4",
          "label": "心都要跳出来了",
          "score": 4,
          "claim_code": "agitation_tendency",
          "is_none": false,
          "exclusive_with": [],
          "evidence_semantic_ref": "claim-dictionary-v3.0.json#agitation_tendency"
        }
      ],
      "evidence_semantic_ref": "claim-dictionary-v3.0.json#agitation_tendency"
    },
    {
      "question_id": "q03",
      "position": 3,
      "prompt": "最近一周，你会不会想事情比较多、脑子里停不下来？",
      "answer_type": "frequency_0_4",
      "required": true,
      "min_selections": null,
      "max_selections": null,
      "options": [
        {
          "option_code": "0",
          "label": "脑子很清爽",
          "score": 0,
          "claim_code": "overthinking_tendency",
          "is_none": false,
          "exclusive_with": [],
          "evidence_semantic_ref": "claim-dictionary-v3.0.json#overthinking_tendency"
        },
        {
          "option_code": "1",
          "label": "偶尔想点事",
          "score": 1,
          "claim_code": "overthinking_tendency",
          "is_none": false,
          "exclusive_with": [],
          "evidence_semantic_ref": "claim-dictionary-v3.0.json#overthinking_tendency"
        },
        {
          "option_code": "2",
          "label": "有点放不下",
          "score": 2,
          "claim_code": "overthinking_tendency",
          "is_none": false,
          "exclusive_with": [],
          "evidence_semantic_ref": "claim-dictionary-v3.0.json#overthinking_tendency"
        },
        {
          "option_code": "3",
          "label": "事情一件接一件",
          "score": 3,
          "claim_code": "overthinking_tendency",
          "is_none": false,
          "exclusive_with": [],
          "evidence_semantic_ref": "claim-dictionary-v3.0.json#overthinking_tendency"
        },
        {
          "option_code": "4",
          "label": "脑子里像在刷弹幕",
          "score": 4,
          "claim_code": "overthinking_tendency",
          "is_none": false,
          "exclusive_with": [],
          "evidence_semantic_ref": "claim-dictionary-v3.0.json#overthinking_tendency"
        }
      ],
      "evidence_semantic_ref": "claim-dictionary-v3.0.json#overthinking_tendency"
    },
    {
      "question_id": "q04",
      "position": 4,
      "prompt": "最近一周，你会不会觉得心情有点低落、想叹气？",
      "answer_type": "frequency_0_4",
      "required": true,
      "min_selections": null,
      "max_selections": null,
      "options": [
        {
          "option_code": "0",
          "label": "心情不错",
          "score": 0,
          "claim_code": "sadness_tendency",
          "is_none": false,
          "exclusive_with": [],
          "evidence_semantic_ref": "claim-dictionary-v3.0.json#sadness_tendency"
        },
        {
          "option_code": "1",
          "label": "偶尔有点小低落",
          "score": 1,
          "claim_code": "sadness_tendency",
          "is_none": false,
          "exclusive_with": [],
          "evidence_semantic_ref": "claim-dictionary-v3.0.json#sadness_tendency"
        },
        {
          "option_code": "2",
          "label": "心里闷闷的",
          "score": 2,
          "claim_code": "sadness_tendency",
          "is_none": false,
          "exclusive_with": [],
          "evidence_semantic_ref": "claim-dictionary-v3.0.json#sadness_tendency"
        },
        {
          "option_code": "3",
          "label": "像压了块小石头",
          "score": 3,
          "claim_code": "sadness_tendency",
          "is_none": false,
          "exclusive_with": [],
          "evidence_semantic_ref": "claim-dictionary-v3.0.json#sadness_tendency"
        },
        {
          "option_code": "4",
          "label": "感觉天都是灰蒙蒙的",
          "score": 4,
          "claim_code": "sadness_tendency",
          "is_none": false,
          "exclusive_with": [],
          "evidence_semantic_ref": "claim-dictionary-v3.0.json#sadness_tendency"
        }
      ],
      "evidence_semantic_ref": "claim-dictionary-v3.0.json#sadness_tendency"
    },
    {
      "question_id": "q05",
      "position": 5,
      "prompt": "最近一周，你会不会觉得心里不太踏实、有点害怕？",
      "answer_type": "frequency_0_4",
      "required": true,
      "min_selections": null,
      "max_selections": null,
      "options": [
        {
          "option_code": "0",
          "label": "心里很踏实",
          "score": 0,
          "claim_code": "fear_tendency",
          "is_none": false,
          "exclusive_with": [],
          "evidence_semantic_ref": "claim-dictionary-v3.0.json#fear_tendency"
        },
        {
          "option_code": "1",
          "label": "偶尔有点小忐忑",
          "score": 1,
          "claim_code": "fear_tendency",
          "is_none": false,
          "exclusive_with": [],
          "evidence_semantic_ref": "claim-dictionary-v3.0.json#fear_tendency"
        },
        {
          "option_code": "2",
          "label": "心里有点不踏实",
          "score": 2,
          "claim_code": "fear_tendency",
          "is_none": false,
          "exclusive_with": [],
          "evidence_semantic_ref": "claim-dictionary-v3.0.json#fear_tendency"
        },
        {
          "option_code": "3",
          "label": "心里直打鼓",
          "score": 3,
          "claim_code": "fear_tendency",
          "is_none": false,
          "exclusive_with": [],
          "evidence_semantic_ref": "claim-dictionary-v3.0.json#fear_tendency"
        },
        {
          "option_code": "4",
          "label": "总觉得要有什么事",
          "score": 4,
          "claim_code": "fear_tendency",
          "is_none": false,
          "exclusive_with": [],
          "evidence_semantic_ref": "claim-dictionary-v3.0.json#fear_tendency"
        }
      ],
      "evidence_semantic_ref": "claim-dictionary-v3.0.json#fear_tendency"
    },
    {
      "question_id": "q06",
      "position": 6,
      "prompt": "下面这些感觉，最近一周有没有出现过？",
      "answer_type": "multi_choice_evidence",
      "required": true,
      "min_selections": 1,
      "max_selections": 5,
      "options": [
        {
          "option_code": "flank_discomfort",
          "label": "胸口附近有时会觉得闷闷的，想长舒一口气",
          "claim_code": "flank_discomfort",
          "is_none": false,
          "exclusive_with": [],
          "score": null,
          "evidence_semantic_ref": "claim-dictionary-v3.0.json#flank_discomfort"
        },
        {
          "option_code": "tendon_stiffness",
          "label": "身体某些部位会觉得紧绷、伸展不开",
          "claim_code": "tendon_stiffness",
          "is_none": false,
          "exclusive_with": [],
          "score": null,
          "evidence_semantic_ref": "claim-dictionary-v3.0.json#tendon_stiffness"
        },
        {
          "option_code": "muscle_cramp",
          "label": "小腿或脚有时会突然抽一下",
          "claim_code": "muscle_cramp",
          "is_none": false,
          "exclusive_with": [],
          "score": null,
          "evidence_semantic_ref": "claim-dictionary-v3.0.json#muscle_cramp"
        },
        {
          "option_code": "eye_discomfort",
          "label": "眼睛有时会觉得干、看久了容易累",
          "claim_code": "eye_discomfort",
          "is_none": false,
          "exclusive_with": [],
          "score": null,
          "evidence_semantic_ref": "claim-dictionary-v3.0.json#eye_discomfort"
        },
        {
          "option_code": "none",
          "label": "都很少出现，很轻松",
          "claim_code": null,
          "is_none": true,
          "exclusive_with": [
            "*"
          ],
          "score": null,
          "evidence_semantic_ref": null
        }
      ]
    },
    {
      "question_id": "q07",
      "position": 7,
      "prompt": "下面这些感觉，最近一周有没有出现过？",
      "answer_type": "multi_choice_evidence",
      "required": true,
      "min_selections": 1,
      "max_selections": 5,
      "options": [
        {
          "option_code": "palpitation_at_rest",
          "label": "安静坐着或躺着时，有时能感觉到自己的心跳",
          "claim_code": "palpitation_at_rest",
          "is_none": false,
          "exclusive_with": [],
          "score": null,
          "evidence_semantic_ref": "claim-dictionary-v3.0.json#palpitation_at_rest"
        },
        {
          "option_code": "palpitation_after_activity",
          "label": "稍微活动一下，心跳就变得比较明显",
          "claim_code": "palpitation_after_activity",
          "is_none": false,
          "exclusive_with": [],
          "score": null,
          "evidence_semantic_ref": "claim-dictionary-v3.0.json#palpitation_after_activity"
        },
        {
          "option_code": "palpitation_night",
          "label": "晚上躺下时，会因为心跳的感觉而不太舒服",
          "claim_code": "palpitation_night",
          "is_none": false,
          "exclusive_with": [],
          "score": null,
          "evidence_semantic_ref": "claim-dictionary-v3.0.json#palpitation_night"
        },
        {
          "option_code": "tongue_tip_discomfort",
          "label": "舌尖有时候会觉得有点疼或有点红",
          "claim_code": "tongue_tip_discomfort",
          "is_none": false,
          "exclusive_with": [],
          "score": null,
          "evidence_semantic_ref": "claim-dictionary-v3.0.json#tongue_tip_discomfort"
        },
        {
          "option_code": "none",
          "label": "都很少出现，很轻松",
          "claim_code": null,
          "is_none": true,
          "exclusive_with": [
            "*"
          ],
          "score": null,
          "evidence_semantic_ref": null
        }
      ]
    },
    {
      "question_id": "q08",
      "position": 8,
      "prompt": "下面这些感觉，最近一周有没有出现过？",
      "answer_type": "multi_choice_evidence",
      "required": true,
      "min_selections": 1,
      "max_selections": 5,
      "options": [
        {
          "option_code": "poor_appetite",
          "label": "胃口一般，到饭点也不太想吃",
          "claim_code": "poor_appetite",
          "is_none": false,
          "exclusive_with": [],
          "score": null,
          "evidence_semantic_ref": "claim-dictionary-v3.0.json#poor_appetite"
        },
        {
          "option_code": "postmeal_bloating",
          "label": "吃一点就觉得胀胀的、撑撑的",
          "claim_code": "postmeal_bloating",
          "is_none": false,
          "exclusive_with": [],
          "score": null,
          "evidence_semantic_ref": "claim-dictionary-v3.0.json#postmeal_bloating"
        },
        {
          "option_code": "loose_stool",
          "label": "上厕所时，大便有时候会比较稀、不太成形",
          "claim_code": "loose_stool",
          "is_none": false,
          "exclusive_with": [],
          "score": null,
          "evidence_semantic_ref": "claim-dictionary-v3.0.json#loose_stool"
        },
        {
          "option_code": "postmeal_heaviness",
          "label": "饭后觉得身体沉沉的、没什么精神，想休息",
          "claim_code": "postmeal_heaviness",
          "is_none": false,
          "exclusive_with": [],
          "score": null,
          "evidence_semantic_ref": "claim-dictionary-v3.0.json#postmeal_heaviness"
        },
        {
          "option_code": "none",
          "label": "都很少出现，很轻松",
          "claim_code": null,
          "is_none": true,
          "exclusive_with": [
            "*"
          ],
          "score": null,
          "evidence_semantic_ref": null
        }
      ]
    },
    {
      "question_id": "q09",
      "position": 9,
      "prompt": "下面这些感觉，最近一周有没有出现过？",
      "answer_type": "multi_choice_evidence",
      "required": true,
      "min_selections": 1,
      "max_selections": 5,
      "options": [
        {
          "option_code": "throat_cough",
          "label": "嗓子有时会觉得干，或有点想清一清",
          "claim_code": "throat_cough",
          "is_none": false,
          "exclusive_with": [],
          "score": null,
          "evidence_semantic_ref": "claim-dictionary-v3.0.json#throat_cough"
        },
        {
          "option_code": "exertional_breathlessness",
          "label": "走路、爬楼时，呼吸会比平时快一点",
          "claim_code": "exertional_breathlessness",
          "is_none": false,
          "exclusive_with": [],
          "score": null,
          "evidence_semantic_ref": "claim-dictionary-v3.0.json#exertional_breathlessness"
        },
        {
          "option_code": "nasal_discomfort",
          "label": "鼻子有时会觉得不通气",
          "claim_code": "nasal_discomfort",
          "is_none": false,
          "exclusive_with": [],
          "score": null,
          "evidence_semantic_ref": "claim-dictionary-v3.0.json#nasal_discomfort"
        },
        {
          "option_code": "voice_change",
          "label": "说话久了会觉得嗓子累、声音变哑",
          "claim_code": "voice_change",
          "is_none": false,
          "exclusive_with": [],
          "score": null,
          "evidence_semantic_ref": "claim-dictionary-v3.0.json#voice_change"
        },
        {
          "option_code": "none",
          "label": "都很少出现，很轻松",
          "claim_code": null,
          "is_none": true,
          "exclusive_with": [
            "*"
          ],
          "score": null,
          "evidence_semantic_ref": null
        }
      ]
    },
    {
      "question_id": "q10",
      "position": 10,
      "prompt": "下面这些感觉，最近一周有没有出现过？",
      "answer_type": "multi_choice_evidence",
      "required": true,
      "min_selections": 1,
      "max_selections": 4,
      "options": [
        {
          "option_code": "lower_back_knee_weakness",
          "label": "腰或腿有时会觉得酸酸的、没什么劲",
          "claim_code": "lower_back_knee_weakness",
          "is_none": false,
          "exclusive_with": [],
          "score": null,
          "evidence_semantic_ref": "claim-dictionary-v3.0.json#lower_back_knee_weakness"
        },
        {
          "option_code": "tinnitus",
          "label": "耳朵有时会有嗡嗡声",
          "claim_code": "tinnitus",
          "is_none": false,
          "exclusive_with": [],
          "score": null,
          "evidence_semantic_ref": "claim-dictionary-v3.0.json#tinnitus"
        },
        {
          "option_code": "nocturia",
          "label": "夜里有时会起来上厕所",
          "claim_code": "nocturia",
          "is_none": false,
          "exclusive_with": [],
          "score": null,
          "evidence_semantic_ref": "claim-dictionary-v3.0.json#nocturia"
        },
        {
          "option_code": "none",
          "label": "都很少出现，很轻松",
          "claim_code": null,
          "is_none": true,
          "exclusive_with": [
            "*"
          ],
          "score": null,
          "evidence_semantic_ref": null
        }
      ]
    }
  ],
  "claim_dictionary_version": "medical_v3.0",
  "review_status": "approved",
  "user_goal": {
    "title": "疗愈诉求",
    "page_kind": "optional_supplement",
    "is_question": false,
    "required": false,
    "skippable": true,
    "max_selections": 2,
    "options": [
      {
        "code": "sleep",
        "label": "帮我睡得安稳一点"
      },
      {
        "code": "relaxation",
        "label": "让我放松、静下来"
      },
      {
        "code": "emotion_regulation",
        "label": "帮我把情绪释放出来"
      },
      {
        "code": "focus",
        "label": "让我更容易专注"
      },
      {
        "code": "energy",
        "label": "帮我恢复点精力"
      },
      {
        "code": "stress_relief",
        "label": "让我减轻点压力"
      },
      {
        "code": "other",
        "label": "其他"
      }
    ],
    "custom_goal_text": {
      "required": false,
      "max_length": 200,
      "independent": true
    },
    "empty_semantics": "user_goal_null",
    "evidence_role": "music_design_preference_only"
  },
  "content_checksum": "sha256:69a01d0753908e3e48e41ea947219818436f24eb4e97aeca260f4b4ca4951031"
}

export default QUESTIONNAIRE_MANIFEST
