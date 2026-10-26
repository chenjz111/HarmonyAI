"""Offline loading of an independently approved, immutable password blocklist.

No bundled production list, network lookup, automatic update or weak fallback.
The deployment must pin the reviewed manifest hash outside the supplied files.
"""
import hashlib
import hmac
import json
from pathlib import Path
import re
from types import MappingProxyType

from .account_password import PasswordPolicy


def _read_bounded(path, limit):
    if path.is_symlink() or not path.is_file():
        raise ValueError()
    with path.open('rb') as source:
        data=source.read(limit+1)
    if len(data)>limit:
        raise ValueError()
    return data


def _unique_object(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError()
        result[key]=value
    return result


def load_reviewed_password_policy(manifest_path, *, approved_manifest_sha256):
    """Return the existing R1 policy only after both pinned artifacts validate.

    A matching hash proves correspondence to the caller's reviewed input; it
    does not itself grant approval or prove dataset completeness/licensing.
    """
    try:
        if not isinstance(approved_manifest_sha256,str) or not re.fullmatch('[0-9a-f]{64}',approved_manifest_sha256):raise ValueError()
        path=Path(manifest_path)
        raw=_read_bounded(path,64*1024)
        digest=hashlib.sha256(raw).hexdigest()
        if not hmac.compare_digest(digest,approved_manifest_sha256):raise ValueError()
        manifest=json.loads(raw.decode('utf-8'),object_pairs_hook=_unique_object)
        fields={'format','version','approval_ref','license_ref','passwords_file','passwords_sha256','entry_count'}
        if not isinstance(manifest,dict) or set(manifest)!=fields or manifest['format']!='harmonyai.password-blocklist.v1':raise ValueError()
        if any(not isinstance(manifest[key],str) or not manifest[key].strip() or len(manifest[key])>512 for key in ['version','approval_ref','license_ref']):raise ValueError()
        name=manifest['passwords_file']
        if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*\.json',name):raise ValueError()
        expected=manifest['passwords_sha256']
        if not isinstance(expected,str) or not re.fullmatch('[0-9a-f]{64}',expected):raise ValueError()
        count=manifest['entry_count']
        if type(count) is not int or count<1:raise ValueError()
        data_path=path.parent/name
        if data_path.resolve().parent!=path.parent.resolve():raise ValueError()
        data=_read_bounded(data_path,32*1024*1024)
        if not hmac.compare_digest(hashlib.sha256(data).hexdigest(),expected):raise ValueError()
        passwords=json.loads(data.decode('utf-8'))
        if not isinstance(passwords,list) or len(passwords)!=count:raise ValueError()
        policy=PasswordPolicy(blocked_passwords=passwords)
        policy.source_info=MappingProxyType({key:manifest[key] for key in ['version','approval_ref','license_ref','entry_count','passwords_sha256']})
        policy.source_info=MappingProxyType({**policy.source_info,'manifest_sha256':digest})
        return policy
    except (OSError,ValueError,TypeError,KeyError,UnicodeError):
        # Do not include dataset entries, source paths or attempted passwords.
        raise ValueError('reviewed password source unavailable') from None
