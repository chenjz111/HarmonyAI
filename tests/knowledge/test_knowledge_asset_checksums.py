"""V3 医学资产 checksum 一致性测试（PR #89 review P0-1）。

验证每个知识资产的「三方一致性」：
  1. 资产文件内嵌的 content_checksum
  2. knowledge-manifest 的 assets 引用
  3. 实际 canonical hash

canonical hash 规则（仓库既有约定）：移除顶层 content_checksum 后，
json.dumps(ensure_ascii=False, sort_keys=True, separators=(",", ":")) 的 sha256。
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE_V3 = ROOT / "knowledge" / "v3"

# manifest 引用的 4 个医学资产（不含 manifest 自身，manifest 不可自引用）
ASSET_FILES = [
    "questionnaire-v3.0.json",
    "claim-dictionary-v3.0.json",
    "organ-mapping-v3.0.json",
    "five-tone-mapping-v3.0.json",
]


def canonical_sha256(obj: dict) -> str:
    """移除顶层 content_checksum 后计算 canonical sha256。"""
    data = {k: v for k, v in obj.items() if k != "content_checksum"}
    serialized = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _load(name: str) -> dict:
    with open(KNOWLEDGE_V3 / name, encoding="utf-8") as f:
        return json.load(f)


def test_each_asset_embedded_checksum_matches_canonical():
    """资产文件内嵌 content_checksum 必须等于 canonical hash。"""
    for name in ASSET_FILES:
        obj = _load(name)
        actual = canonical_sha256(obj)
        assert obj.get("content_checksum") == actual, (
            f"{name} 内嵌 content_checksum 失效：声明={obj.get('content_checksum')} 实际={actual}"
        )


def test_manifest_references_match_each_asset_canonical():
    """manifest 引用的每个 asset checksum 必须等于该文件 canonical hash。"""
    manifest = _load("knowledge-manifest-v3.0.json")
    refs = {a["asset"]: a["content_checksum"] for a in manifest["assets"]}
    assert set(refs) == set(ASSET_FILES), (
        f"manifest assets 应恰为 4 个医学资产，实际={sorted(refs)}"
    )
    for name in ASSET_FILES:
        actual = canonical_sha256(_load(name))
        assert refs[name] == actual, (
            f"manifest 引用失效：{name} 引用={refs[name]} 实际={actual}"
        )


def test_manifest_does_not_self_reference_and_is_verifiable():
    """manifest 不得以不可校验文本自引用；自身 checksum 必须可校验。"""
    manifest = _load("knowledge-manifest-v3.0.json")
    asset_names = [a["asset"] for a in manifest["assets"]]
    assert "knowledge-manifest-v3.0.json" not in asset_names, "manifest 不应把自己列为 asset"
    for a in manifest["assets"]:
        assert a["content_checksum"].startswith("sha256:"), (
            f"{a['asset']} 引用必须是可校验 sha256，而非文本占位"
        )
    assert manifest["content_checksum"] == canonical_sha256(manifest), (
        "manifest 顶层 content_checksum 与 canonical hash 不一致"
    )
