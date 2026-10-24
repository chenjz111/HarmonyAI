import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const surveyPath = new URL('../pages/survey/survey.vue', import.meta.url)

async function loadSurveyComponent() {
  const source = await readFile(surveyPath, 'utf8')
  const match = source.match(/<script>([\s\S]*?)<\/script>/)
  assert.ok(match, 'survey.vue must contain a script block')

  const executable = match[1]
    .replace(/^import .*$/gm, '')
    .replace('export default', 'return')

  return new Function(executable)()
}

test('survey page defines narrative plus three questionnaire steps', async () => {
  const component = await loadSurveyComponent()
  const state = component.data()

  assert.equal(state.totalSteps, 4)
  assert.equal(state.steps.length, 4)
  assert.equal(state.steps[0].isNarrative, true)
  assert.deepEqual(
    state.steps.slice(1).map((step) => step.questions.length),
    [12, 8, 10],
  )
})
