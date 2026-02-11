# RocketMQ知识初始化功能说明

## 概述

本系统已从硬编码的知识内容改为从文件系统读取RocketMQ知识。知识文件存储在`knowledge/`目录中，系统会自动扫描、解析和分类这些文件。

## 目录结构

知识文件应按照以下目录结构组织：

```
knowledge/
├── 2026-02-12-01/           # 日期版本目录
│   ├── 00-introduction/     # 介绍类知识
│   │   ├── _category_.json  # 分类元数据
│   │   ├── 01whychoose.md   # 知识文件
│   │   └── 02whatis.md
│   ├── 01-quickstart/       # 快速开始类知识
│   │   ├── _category_.json
│   │   └── 01quickstart.md
│   ├── 02-producer/          # 生产者相关知识
│   │   ├── _category_.json
│   │   └── 01concept1.md
│   └── ...                  # 其他分类
```

## 知识文件格式

### Markdown文件格式

每个知识文件应为标准的Markdown格式，系统会自动解析：

```markdown
# 标题

## 子标题

内容...

### 代码示例

```shell
命令示例
```

### 注意事项

- 重要提示
```

### 分类元数据文件

每个分类目录应包含`_category_.json`文件：

```json
{
  "label": "分类名称",
  "position": 0
}
```

## 自动分类机制

系统会根据以下规则自动分类知识：

### 1. 基于目录名称分类
- `introduction` → 介绍类知识
- `quickstart` → 快速开始指南
- `producer` → 生产者相关
- `consumer` → 消费者相关
- `deployment` → 部署配置
- `bestPractice` → 最佳实践

### 2. 基于内容关键词分类
- 包含"排查"、"问题"、"错误" → 故障排查指南
- 包含"配置"、"安装"、"部署" → 配置指南
- 包含"最佳"、"实践"、"指南" → 最佳实践

## 使用方法

### 1. 初始化知识库

```python
from pathlib import Path
from nanobot.knowledge.rocketmq_init import initialize_rocketmq_knowledge

# 初始化知识库
workspace = Path("/path/to/workspace")
count = initialize_rocketmq_knowledge(workspace)
print(f"已加载 {count} 个知识项")
```

### 2. 手动添加知识文件

```python
from nanobot.knowledge.rocketmq_init import get_knowledge_categories, parse_markdown_file

# 解析单个文件
file_path = Path("knowledge/2026-02-12-01/00-introduction/01whychoose.md")
knowledge_item = parse_markdown_file(file_path)

# 获取所有分类
base_path = Path.cwd()
categories = get_knowledge_categories(base_path)
```

## 测试功能

系统提供了测试脚本验证知识初始化功能：

```bash
python test_rocketmq_knowledge.py
```

## 版本控制

- **当前版本**: 1.0.0
- **支持的知识类型**: 故障排查指南、配置指南、最佳实践、诊断检查器
- **文件格式支持**: Markdown (.md, .MD)
- **编码支持**: UTF-8

## 故障排除

### 1. 知识文件未加载
- 检查knowledge目录是否存在
- 验证目录结构是否正确
- 确认文件编码为UTF-8

### 2. 分类不正确
- 检查`_category_.json`文件格式
- 确认目录命名规范
- 验证内容关键词匹配

### 3. 初始化失败
- 检查文件权限
- 验证路径配置
- 查看错误日志

## 扩展功能

系统支持以下扩展功能：

1. **动态知识更新**: 修改knowledge目录后，重新初始化即可更新知识库
2. **多版本支持**: 通过日期目录管理不同版本的知识
3. **自定义分类**: 通过修改分类元数据文件自定义知识组织方式
4. **内容过滤**: 基于标签和关键词进行知识检索和过滤

## 最佳实践

1. **保持目录结构一致**: 使用标准的日期-分类结构
2. **规范文件命名**: 使用有意义的文件名和标题
3. **添加适当标签**: 在内容中包含相关关键词便于分类
4. **定期更新**: 根据RocketMQ版本更新知识内容
5. **版本控制**: 使用Git等工具管理知识文件变更