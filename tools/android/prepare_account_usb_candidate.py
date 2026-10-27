"""Prepare a disposable NONPRODUCTION source input, never submit/build/install."""
from pathlib import Path
import json,subprocess,shutil,hashlib
ROOT=Path(__file__).resolve().parents[2]
EVIDENCE=Path('C:/Users/ASUS/HarmonyAI-s7-m1-evidence-20261024/android-account-usb-20261026')
DEST=EVIDENCE/'HarmonyAI-account-usb-acceptance'
assert not DEST.exists(),'Preserve existing candidate; do not overwrite'
files=subprocess.check_output(['git','ls-files','--','frontend'],cwd=ROOT,text=True).splitlines()
extra=['frontend/common/android-native-bridge.js','frontend/AndroidManifest.xml']
extra += [str(p.relative_to(ROOT)).replace('\\','/') for folder in ['frontend/uni_modules/harmonyai-account-native','frontend/platform-acceptance'] for p in (ROOT/folder).rglob('*') if p.is_file()]
for name in sorted(set(files+extra)):
 relative=Path(name).relative_to('frontend')
 if relative.parts[0] in {'tests','unpackage','node_modules','.hbuilderx','nativeResources'} or relative.name.startswith('.env'):continue
 assert relative.suffix.lower() not in {'.key','.jks','.keystore','.p12','.pfx','.pem'}
 source=ROOT/name
 if not source.is_file():continue
 target=DEST/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
# Existing immutable question artifacts are imported from ../../knowledge.
for name in ['questionnaire-v2.1.json','questionnaire-v2.2.json','quick-state-questionnaire-v1.json']:
 question=ROOT/'knowledge'/name;question_target=EVIDENCE/'knowledge'/name
 question_target.parent.mkdir(exist_ok=True);shutil.copy2(question,question_target)
 assert question.read_bytes()==question_target.read_bytes()
manifest=json.loads((DEST/'manifest.json').read_text(encoding='utf-8'))
manifest['name']='HarmonyAI账号验收';manifest['versionCode']='101'
manifest['app-plus']['distribute']['android']['minSdkVersion']=24
(DEST/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
pages=json.loads((DEST/'pages.json').read_text(encoding='utf-8'))
pages['pages'].insert(0,{'path':'platform-acceptance/android-native','style':{'navigationBarTitleText':'非生产原生验收'}})
(DEST/'pages.json').write_text(json.dumps(pages,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(DEST/'.env.production.local').write_text('VITE_API_BASE_URL=https://127.0.0.1:8443\n',encoding='utf-8')
raw=DEST/'nativeResources/android/res/raw';raw.mkdir(parents=True,exist_ok=True)
cert=(EVIDENCE/'ca-public.pem').read_bytes();assert b'BEGIN CERTIFICATE' in cert and b'PRIVATE KEY' not in cert
(raw/'harmonyai_usb_ca.pem').write_bytes(cert)
xml=DEST/'nativeResources/android/res/xml';xml.mkdir(parents=True,exist_ok=True)
(xml/'harmonyai_network_security_config.xml').write_text('''<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
 <base-config cleartextTrafficPermitted="false"><trust-anchors><certificates src="system" /></trust-anchors></base-config>
 <domain-config cleartextTrafficPermitted="false">
  <domain includeSubdomains="false">127.0.0.1</domain>
  <trust-anchors><certificates src="@raw/harmonyai_usb_ca" /></trust-anchors>
 </domain-config>
</network-security-config>
''',encoding='utf-8')
record={'source':str(ROOT),'candidate':str(DEST),'appid':manifest['appid'],'package':'com.harmonyai.s7test','versionCode':101,'minimum_test_android_sdk':24,'registered_enabled':False,'native_checks':'NOT RUN','cloud_build':'NOT RUN','phone_install':'NOT RUN','test_CA_sha256':hashlib.sha256(cert).hexdigest(),'files':len(list(DEST.rglob('*')))}
# Prevent signing or private TLS material from ever entering the candidate.
assert not any(p.suffix.lower() in {'.jks','.keystore','.key','.p12','.pfx'} for p in DEST.rglob('*') if p.is_file())
(EVIDENCE/'candidate-input.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
print(json.dumps(record))
