# 日志增强总结

## 概述

已在 nanobot 的核心代码路径中添加了详细的日志输出，方便调试和监控系统运行状态。

## 添加的日志位置

### 1. Agent Loop (`nanobot/agent/loop.py`)

#### 消息接收
- `[LOOP] 📥 Received user message`: 接收到用户消息的完整内容

#### 迭代过程
- `[LOOP] 🔄 Agent iteration X/Y`: 当前迭代次数
- `[LOOP] 📝 Context messages count`: 上下文消息数量
- `[LOOP] 💬 Last user message`: 最后一条用户消息预览

#### LLM 调用
- `[LOOP] 🤖 Calling LLM with model`: 调用的模型名称
- `[LOOP] 🤖 LLM response`: LLM 返回的内容预览
- `[LOOP] 🔧 LLM requested X tool call(s)`: 请求的工具调用数量
- `[LOOP] ✅ LLM provided final response`: LLM 提供了最终响应

#### 工具执行
- `[LOOP] 🔧 Executing tool`: 执行的工具名称
- `[LOOP] 🔧 Tool arguments`: 工具参数（最多 500 字符）
- `[LOOP] 🔧 Tool result`: 工具执行结果（最多 300 字符）

#### 最终响应
- `[LOOP] 📤 Final response generated`: 最终响应长度
- `[LOOP] 📤 Response preview`: 响应内容预览

### 2. 知识库工具 (`nanobot/agent/tools/knowledge.py`)

#### 搜索请求
- `[KNOWLEDGE] 🔍 Search request`: 搜索请求的所有参数
  - Domain（领域）
  - Query（查询文本）
  - Category（分类）
  - Tags（标签）
  - Limit（结果数量限制）

#### 搜索结果
- `[KNOWLEDGE] 📊 Search results`: 找到的结果数量
- `[KNOWLEDGE] ⚠️  No knowledge found`: 未找到知识
- `[KNOWLEDGE] X. Title (score: Y)`: 每个结果的标题和相似度分数
- `[KNOWLEDGE] ✅ Returning X chars`: 返回的格式化结果长度
- `[KNOWLEDGE] ❌ Error`: 搜索错误信息

### 3. 知识库存储 (`nanobot/knowledge/store.py`)

#### 搜索开始
- `[KNOWLEDGE_STORE] 🔍 开始语义检索`: 开始语义检索
  - Query（查询文本）
  - Domain（领域）
  - Category（分类）
  - Tags（标签）
  - Top K（返回数量）

#### 向量化过程
- `[KNOWLEDGE_STORE] 🧮 开始向量化查询文本`: 开始向量化
- `[KNOWLEDGE_STORE] ✅ 查询向量化完成`: 向量化完成
  - 耗时（秒）
  - 向量维度

#### 搜索执行
- `[KNOWLEDGE_STORE] 📚 将在 X 个集合中搜索`: 搜索的集合数量
- `[KNOWLEDGE_STORE] 🔎 相似度搜索完成`: 搜索完成
  - 耗时（秒）
  - 找到的分块结果数量

#### 搜索结果
- `[KNOWLEDGE_STORE] ✅ 语义检索完成`: 检索完成
  - 返回结果数
  - 总耗时
- `[KNOWLEDGE_STORE] X. Title (相似度: Y)`: 前 3 个结果的标题和相似度

## 日志示例

### 完整的知识库搜索流程

```
[KNOWLEDGE] 🔍 Search request:
[KNOWLEDGE]   - Domain: rocketmq
[KNOWLEDGE]   - Query: 消息发送失败怎么办
[KNOWLEDGE]   - Category: None
[KNOWLEDGE]   - Tags: None
[KNOWLEDGE]   - Limit: 10

[KNOWLEDGE_STORE] 🔍 开始语义检索:
[KNOWLEDGE_STORE]   - Query: '消息发送失败怎么办'
[KNOWLEDGE_STORE]   - Domain: rocketmq
[KNOWLEDGE_STORE]   - Category: None
[KNOWLEDGE_STORE]   - Tags: None
[KNOWLEDGE_STORE]   - Top K: 5

[KNOWLEDGE_STORE] 🧮 开始向量化查询文本...
[KNOWLEDGE_STORE] ✅ 查询向量化完成，耗时: 0.037秒，向量维度: 384

[KNOWLEDGE_STORE] 📚 将在 1 个集合中搜索
[KNOWLEDGE_STORE] 🔎 相似度搜索完成，耗时: 0.003秒，找到 3 个分块结果

[KNOWLEDGE_STORE] ✅ 语义检索完成:
[KNOWLEDGE_STORE]   - 返回结果数: 3
[KNOWLEDGE_STORE]   - 总耗时: 0.040秒
[KNOWLEDGE_STORE]   1. 消息发送失败排查指南 (相似度: 0.0748)
[KNOWLEDGE_STORE]   2. RocketMQ知识库初始化 (相似度: 0.0373)
[KNOWLEDGE_STORE]   3. Broker 配置优化 (相似度: 0.0360)

[KNOWLEDGE] 📊 Search results: 3 items found
[KNOWLEDGE]   1. 消息发送失败排查指南 (score: 0.0748)
[KNOWLEDGE]   2. RocketMQ知识库初始化 (score: 0.0373)
[KNOWLEDGE]   3. Broker 配置优化 (score: 0.0360)
[KNOWLEDGE] ✅ Returning 1234 chars of formatted results
```

### Agent Loop 流程

```
[LOOP] 📥 Received user message: 如何解决 RocketMQ 消息发送失败的问题？

[LOOP] 🔄 Agent iteration 1/20
[LOOP] 📝 Context messages count: 3
[LOOP] 💬 Last user message: 如何解决 RocketMQ 消息发送失败的问题？

[LOOP] 🤖 Calling LLM with model: gpt-4
[LOOP] 🤖 LLM response: 我需要搜索知识库来获取相关信息...
[LOOP] 🔧 LLM requested 1 tool call(s)
[LOOP] 🔧   - Tool: knowledge_search

[LOOP] 🔧 Executing tool: knowledge_search
[LOOP] 🔧 Tool arguments: {"domain":"rocketmq","query":"消息发送失败"}
[LOOP] 🔧 Tool result: Found 3 knowledge items: ...

[LOOP] 🔄 Agent iteration 2/20
[LOOP] 🤖 Calling LLM with model: gpt-4
[LOOP] 🤖 LLM response: 根据知识库的信息，消息发送失败的排查步骤如下...
[LOOP] ✅ LLM provided final response (no tool calls)

[LOOP] 📤 Final response generated (length: 456 chars)
[LOOP] 📤 Response preview: 根据知识库的信息，消息发送失败的排查步骤如下：1. 检查网络连接...
```

## 使用建议

1. **调试时**: 查看完整日志输出，了解每一步的执行情况
2. **性能分析**: 关注耗时日志，识别性能瓶颈
3. **问题排查**: 通过日志追踪请求流程，定位问题所在
4. **监控**: 可以基于这些日志建立监控指标

## 测试

运行 `test_logging.py` 可以验证日志输出：

```bash
python test_logging.py
```

## 注意事项

- 所有日志使用 `loguru` 库，确保日志格式统一
- 日志级别为 `INFO`，生产环境可以调整为 `WARNING` 或 `ERROR`
- 敏感信息（如完整的用户输入）会被截断，只显示预览
- 向量和大型数据结构只显示关键信息（如维度、长度）
