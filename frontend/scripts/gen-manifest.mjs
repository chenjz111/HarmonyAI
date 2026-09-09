import { readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';

const inputPath = resolve('../knowledge/v3/questionnaire-v3.0.1.json');
const outputPath = resolve('../frontend/common/questionnaire-v3-manifest.js');

const data = JSON.parse(readFileSync(inputPath, 'utf8'));

const content = `/**
 * 五脏状态问卷权威清单（自动生成，禁止修改）
 * 生成自: knowledge/v3/questionnaire-v3.0.1.json
 */
export const QUESTIONNAIRE_MANIFEST = ${JSON.stringify(data, null, 2)};
export default QUESTIONNAIRE_MANIFEST;
`;

writeFileSync(outputPath, content);
console.log('Manifest generated.');
