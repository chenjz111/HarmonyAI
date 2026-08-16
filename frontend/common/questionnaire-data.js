import questionnaireArtifact from "../../knowledge/questionnaire-v2.1.json"
import questionnaireV22Artifact from "../../knowledge/questionnaire-v2.2.json"
import quickStateArtifact from "../../knowledge/quick-state-questionnaire-v1.json"

function moduleList(artifact) {
  return Object.entries(artifact.modules || {}).map(([code, value]) => ({
    code,
    name: value.name,
    question_count: value.count,
  }))
}

export const questionnaireV21 = {
  ...questionnaireArtifact,
  modules: moduleList(questionnaireArtifact),
}

export const questionnaireV22 = {
  ...questionnaireV22Artifact,
  modules: moduleList(questionnaireV22Artifact),
}

export const quickStateV1 = {
  ...quickStateArtifact,
  modules: moduleList(quickStateArtifact),
}