# Chroma RAG Store（Sprint 1）

## 目标

为 HarmonyAI 提供可本地持久化的最小 Chroma 知识检索闭环：写入演示知识块、重新打开数据库后检索，并返回可追溯的来源元数据。

## 范围

- 使用 `chromadb.PersistentClient` 保存集合。
- 随代码提供 3 条演示知识块，验证真实查询链路。
- 暴露写入、查询和集合计数接口。
- 用内置的确定性哈希 embedding 保障离线、可复现的 Sprint 1 演示。

不包含 Qwen 调用、医学诊断、正式文献批量入库或 BGE-M3 模型下载。后续可在不改变调用方的前提下将内置 embedding 替换为 BGE-M3 并导入正式切块数据。

## 数据结构

每条知识块使用唯一 `chunk_id` 作为 Chroma document ID，并保存：

```json
{
  "chunk_id": "demo_001",
  "text": "演示知识内容",
  "metadata": {
    "knowledge_id": "demo_001",
    "source_type": "demo",
    "credibility_level": "D",
    "applicable_emotions": "anxiety"
  }
}
```

Chroma metadata 只存标量字段；数组类标签在导入时以 JSON 字符串保存，避免 Chroma metadata 类型限制。

## 接口

- `ChromaKnowledgeStore(persist_directory, collection_name="harmony_knowledge", embedding_version="hash-v1")`
- `upsert(chunks)`：按 `chunk_id` 幂等写入知识块。
- `query(query_text, limit=3)`：返回 `text`、`metadata`、`distance` 和由距离换算的 `score`。
- `count()`：返回当前集合的条目数。

## 验收与安全

测试必须证明：

1. 3 条种子知识可以写入 Chroma；
2. 新建 Store 指向相同目录后仍能读到写入内容；
3. 对“焦虑、角调”等查询至少命中对应知识；
4. 检索结果带有来源和证据等级元数据。

演示数据明确标为 `demo` / `D` 级，仅用于验证工程链路，不能作为临床建议或正式证据。

`embedding_version` 会被加入 Chroma collection 名称。切换到 BGE-M3 时必须使用新的版本名（例如 `bge-m3-v1`）并重新入库，避免不同维度的向量混入同一集合。
