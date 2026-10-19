"""Version-isolated digest of an already-normalized V3.1 feedback request."""

from hashlib import sha256
import json
from typing import Mapping


_DOMAIN = b"feedback_v3.1\0"


def fingerprint_feedback_request(normalized_payload: Mapping[str, object]) -> str:
    canonical = json.dumps(
        normalized_payload, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")
    return "sha256:" + sha256(_DOMAIN + canonical).hexdigest()
