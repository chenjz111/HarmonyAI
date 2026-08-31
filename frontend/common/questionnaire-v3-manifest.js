/**
 * 五脏状态问卷 V3.0 权威清单（PR #89 医学审核批准版本）
 * 来源：knowledge/v3/questionnaire-v3.0.json（单一事实来源，前端逐字同步）
 * - review_status=approved，content_checksum 与后端一致
 * - q01-q05 为频率题（frequency_0_4，值 0..4 整数）
 * - q06-q10 为多选题（multi_choice_evidence，含互斥的"都很少出现"选项）
 * 注意：题目文案属于医学审核内容，任何人不得在前端擅自增删改
 */

export const FREQUENCY_OPTIONS = [
  {
    "value": 0,
    "label": "没有或几乎没有"
  },
  {
    "value": 1,
    "label": "偶尔有"
  },
  {
    "value": 2,
    "label": "有时有"
  },
  {
    "value": 3,
    "label": "经常有"
  },
  {
    "value": 4,
    "label": "几乎总是"
  }
]

export const QUESTIONNAIRE_MANIFEST = {
  "schema_id": "questionnaire_v3",
  "schema_version": "3.0.0",
  "manifest_version": "medical_v3.0",
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
      "options": []
    },
    {
      "question_id": "q02",
      "position": 2,
      "prompt": "最近一周，你会不会比较容易开心、兴奋，甚至有点收不住？",
      "answer_type": "frequency_0_4",
      "required": true,
      "min_selections": null,
      "max_selections": null,
      "options": []
    },
    {
      "question_id": "q03",
      "position": 3,
      "prompt": "最近一周，你会不会想事情比较多、脑子里停不下来？",
      "answer_type": "frequency_0_4",
      "required": true,
      "min_selections": null,
      "max_selections": null,
      "options": []
    },
    {
      "question_id": "q04",
      "position": 4,
      "prompt": "最近一周，你会不会觉得心情有点低落、想叹气？",
      "answer_type": "frequency_0_4",
      "required": true,
      "min_selections": null,
      "max_selections": null,
      "options": []
    },
    {
      "question_id": "q05",
      "position": 5,
      "prompt": "最近一周，你会不会觉得心里不太踏实、有点害怕？",
      "answer_type": "frequency_0_4",
      "required": true,
      "min_selections": null,
      "max_selections": null,
      "options": []
    },
    {
      "question_id": "q06",
      "position": 6,
      "prompt": "下面这些感觉，最近一周有没有出现过？（没有就选“都很少出现”，不用勉强）",
      "answer_type": "multi_choice_evidence",
      "required": true,
      "min_selections": 1,
      "max_selections": 5,
      "options": [
        {
          "option_code": "flank_discomfort",
          "label": "两侧肋骨（胁肋）附近有时会觉得闷闷的、胀胀的，想长舒一口气",
          "claim_code": "flank_discomfort",
          "is_none": false,
          "exclusive_with": []
        },
        {
          "option_code": "tendon_stiffness",
          "label": "身体某些部位会觉得紧绷、伸展不开",
          "claim_code": "tendon_stiffness",
          "is_none": false,
          "exclusive_with": []
        },
        {
          "option_code": "muscle_cramp",
          "label": "小腿或脚有时会突然抽一下",
          "claim_code": "muscle_cramp",
          "is_none": false,
          "exclusive_with": []
        },
        {
          "option_code": "eye_discomfort",
          "label": "眼睛有时会觉得干、看久了容易累",
          "claim_code": "eye_discomfort",
          "is_none": false,
          "exclusive_with": []
        },
        {
          "option_code": "none",
          "label": "都很少出现，很轻松",
          "claim_code": null,
          "is_none": true,
          "exclusive_with": [
            "*"
          ]
        }
      ]
    },
    {
      "question_id": "q07",
      "position": 7,
      "prompt": "下面这些感觉，最近一周有没有出现过？（没有就选“都很少出现”，不用勉强）",
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
          "exclusive_with": []
        },
        {
          "option_code": "palpitation_after_activity",
          "label": "稍微活动一下，心跳就变得比较明显",
          "claim_code": "palpitation_after_activity",
          "is_none": false,
          "exclusive_with": []
        },
        {
          "option_code": "palpitation_night",
          "label": "晚上躺下时，会因为心跳的感觉而不太舒服",
          "claim_code": "palpitation_night",
          "is_none": false,
          "exclusive_with": []
        },
        {
          "option_code": "tongue_tip_discomfort",
          "label": "舌尖有时候会觉得有点疼或有点红",
          "claim_code": "tongue_tip_discomfort",
          "is_none": false,
          "exclusive_with": []
        },
        {
          "option_code": "none",
          "label": "都很少出现，很轻松",
          "claim_code": null,
          "is_none": true,
          "exclusive_with": [
            "*"
          ]
        }
      ]
    },
    {
      "question_id": "q08",
      "position": 8,
      "prompt": "下面这些感觉，最近一周有没有出现过？（没有就选“都很少出现”，不用勉强）",
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
          "exclusive_with": []
        },
        {
          "option_code": "postmeal_bloating",
          "label": "吃一点就觉得胀胀的、撑撑的",
          "claim_code": "postmeal_bloating",
          "is_none": false,
          "exclusive_with": []
        },
        {
          "option_code": "loose_stool",
          "label": "上厕所时，大便有时候会比较稀、不太成形",
          "claim_code": "loose_stool",
          "is_none": false,
          "exclusive_with": []
        },
        {
          "option_code": "postmeal_heaviness",
          "label": "饭后觉得身体沉沉的、没什么精神，想休息",
          "claim_code": "postmeal_heaviness",
          "is_none": false,
          "exclusive_with": []
        },
        {
          "option_code": "none",
          "label": "都很少出现，很轻松",
          "claim_code": null,
          "is_none": true,
          "exclusive_with": [
            "*"
          ]
        }
      ]
    },
    {
      "question_id": "q09",
      "position": 9,
      "prompt": "下面这些感觉，最近一周有没有出现过？（没有就选“都很少出现”，不用勉强）",
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
          "exclusive_with": []
        },
        {
          "option_code": "exertional_breathlessness",
          "label": "和平时相比，走路、爬楼时明显更容易气喘、气不够用（比以前明显）",
          "claim_code": "exertional_breathlessness",
          "is_none": false,
          "exclusive_with": []
        },
        {
          "option_code": "nasal_discomfort",
          "label": "鼻子有时会觉得不通气",
          "claim_code": "nasal_discomfort",
          "is_none": false,
          "exclusive_with": []
        },
        {
          "option_code": "voice_change",
          "label": "说话久了会觉得嗓子累、声音变哑",
          "claim_code": "voice_change",
          "is_none": false,
          "exclusive_with": []
        },
        {
          "option_code": "none",
          "label": "都很少出现，很轻松",
          "claim_code": null,
          "is_none": true,
          "exclusive_with": [
            "*"
          ]
        }
      ]
    },
    {
      "question_id": "q10",
      "position": 10,
      "prompt": "下面这些感觉，最近一周有没有出现过？（没有就选“都很少出现”，不用勉强）",
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
          "exclusive_with": []
        },
        {
          "option_code": "tinnitus",
          "label": "耳朵有时会有嗡嗡声",
          "claim_code": "tinnitus",
          "is_none": false,
          "exclusive_with": []
        },
        {
          "option_code": "nocturia",
          "label": "夜里有时会起来上厕所",
          "claim_code": "nocturia",
          "is_none": false,
          "exclusive_with": []
        },
        {
          "option_code": "none",
          "label": "都很少出现，很轻松",
          "claim_code": null,
          "is_none": true,
          "exclusive_with": [
            "*"
          ]
        }
      ]
    }
  ],
  "claim_dictionary_version": "medical_v3.0",
  "content_checksum": "sha256:fef9830e3d269236a58213f95e2fd3449baf0ef52c0ffd74f516792f96910211",
  "review_status": "approved"
}

export default QUESTIONNAIRE_MANIFEST
