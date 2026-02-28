"""Text chunking for long documents."""

import logging
from typing import Any, Dict, List

from langchain_text_splitters import RecursiveCharacterTextSplitter
from loguru import logger

class TextChunker:
    """文本分块器，将长文本分割为语义块."""

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200, 
                 smart_chunking: bool = False, preserve_structure: bool = False):
        """初始化分块器.
        
        Args:
            chunk_size: 块大小（字符数）
            chunk_overlap: 块重叠大小（字符数）
            smart_chunking: 启用智能分割
            preserve_structure: 保持文档结构
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.smart_chunking = smart_chunking
        self.preserve_structure = preserve_structure
        self.splitter = None
        self._init_splitter()

    def _init_splitter(self) -> None:
        """初始化文本分割器，配置中文友好的分隔符."""
        if self.smart_chunking and self.preserve_structure:
            # 智能分割：优先保持文档结构完整性
            separators = [
                "\n<!-- CHUNK_BOUNDARY -->\n",  # 手动分块标记（最高优先级）
                "\n\n### ",  # 三级标题（操作步骤）
                "\n\n#### ",  # 四级标题（具体组件）
                "\n\n```",  # 代码块
                "\n\n",  # 段落分隔符
                "\n### ",  # 三级标题（无前导换行）
                "\n#### ",  # 四级标题（无前导换行）
                "\n```",  # 代码块（无前导换行）
                "\n",  # 换行符
                "。",  # 中文句号
                "！",  # 中文感叹号
                "？",  # 中文问号
                "；",  # 中文分号
                ".",  # 英文句号
                "!",  # 英文感叹号
                "?",  # 英文问号
                ";",  # 英文分号
                "，",  # 中文逗号
                ",",  # 英文逗号
                " ",  # 空格
                "",  # 字符级别分割
            ]
            logger.info("启用智能分割和结构保持模式")
        else:
            # 标准分割：使用原有的分隔符
            separators = [
                "\n\n",  # 段落分隔符
                "\n",  # 换行符
                "。",  # 中文句号
                "！",  # 中文感叹号
                "？",  # 中文问号
                "；",  # 中文分号
                ".",  # 英文句号
                "!",  # 英文感叹号
                "?",  # 英文问号
                ";",  # 英文分号
                "，",  # 中文逗号
                ",",  # 英文逗号
                " ",  # 空格
                "",  # 字符级别分割
            ]
            
        # 使用递归字符分割策略，优先在段落、句子边界处分块
        # 分隔符按优先级排序：段落 > 句子 > 标点 > 空格 > 字符
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=separators,
            keep_separator=True,  # 保留分隔符
            length_function=len,
        )
        
        # 添加调试信息
        if self.smart_chunking and self.preserve_structure:
            logger.info(f"智能分割分隔符: {separators[:5]}...")  # 只显示前5个
        
        logger.info(
            f"文本分块器初始化完成: chunk_size={self.chunk_size}, "
            f"chunk_overlap={self.chunk_overlap}, "
            f"smart_chunking={self.smart_chunking}, "
            f"preserve_structure={self.preserve_structure}"
        )

    def chunk_text(self, text: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """分块文本并保留元数据.
        
        Args:
            text: 输入文本
            metadata: 元数据（id, domain, category, title, tags 等）
            
        Returns:
            分块结果列表，每个元素包含 text 和 metadata
            如果文本长度不超过 chunk_size，返回单个块
        """
        if not text or not text.strip():
            logger.warning("尝试分块空文本，返回空列表")
            return []

        # 检测是否包含手动分块标记
        if "<!-- CHUNK_BOUNDARY -->" in text:
            logger.info(f"检测到手动分块标记 CHUNK_BOUNDARY，文档: {metadata.get('title', 'Unknown')}")
            chunk_count = text.count("<!-- CHUNK_BOUNDARY -->")
            logger.info(f"CHUNK_BOUNDARY 标记数量: {chunk_count}")

        # 如果文本长度不超过 chunk_size，不需要分块
        if len(text) <= self.chunk_size:
            logger.debug(f"文本长度 {len(text)} 不超过 chunk_size {self.chunk_size}，不分块")
            return [{
                "text": text,
                "metadata": {
                    **metadata,
                    "chunk_index": 0,
                    "total_chunks": 1,
                }
            }]

        # 使用智能分块或标准分块
        try:
            if self.smart_chunking and self.preserve_structure:
                chunks = self._smart_chunk_text(text)
            else:
                chunks = self.splitter.split_text(text)
                
            logger.info(f"文本分块完成: 原始长度={len(text)}, 分块数={len(chunks)}")

            # 打印原始分块的详细信息
            logger.debug("=== 原始分块详情 ===")
            for i, chunk in enumerate(chunks):
                chunk_preview = chunk.replace('\n', '\\n')[:100]
                logger.debug(f"原始Chunk {i+1}: 长度={len(chunk)}, 预览='{chunk_preview}...'")
                if "<!-- CHUNK_BOUNDARY -->" in chunk:
                    logger.debug(f"  ⚠️ Chunk {i+1} 包含CHUNK_BOUNDARY标记")

            # 为每个分块添加元数据
            result = []
            for i, chunk in enumerate(chunks):
                # 过滤掉只包含CHUNK_BOUNDARY标记的空chunk
                clean_chunk = chunk.replace("<!-- CHUNK_BOUNDARY -->", "").strip()
                if len(clean_chunk) < 10:  # 过滤掉内容太少的chunk
                    logger.debug(f"跳过内容过少的chunk {i+1}: {len(clean_chunk)} 字符, 内容='{clean_chunk}'")
                    continue
                    
                result.append({
                    "text": chunk,
                    "metadata": {
                        **metadata,  # 保留原始元数据
                        "chunk_index": len(result),  # 重新编号
                        "total_chunks": len(chunks),  # 暂时使用原始数量，后面会更新
                    }
                })

            # 更新总chunk数量
            for item in result:
                item["metadata"]["total_chunks"] = len(result)

            # 打印最终分块的详细信息
            logger.debug("=== 最终分块详情 ===")
            for i, item in enumerate(result):
                chunk = item["text"]
                chunk_preview = chunk.replace('\n', '\\n')
                has_boundary = "<!-- CHUNK_BOUNDARY -->" in chunk
                logger.debug(f"最终Chunk {i+1}: 长度={len(chunk)}, BOUNDARY={has_boundary}")
                logger.debug(f"  全部chunk内容: {chunk_preview}")
                
                # 如果chunk包含标题，特别标注
                if any(marker in chunk for marker in ["####", "###", "**步骤"]):
                    titles = []
                    if "####" in chunk:
                        titles.append("四级标题")
                    if "###" in chunk:
                        titles.append("三级标题")
                    if "**步骤" in chunk:
                        titles.append("步骤标记")
                    logger.debug(f"  📋 包含结构: {', '.join(titles)}")

            logger.info(f"过滤后的分块数量: {len(result)} (原始: {len(chunks)})")
            return result

        except Exception as e:
            logger.error(f"文本分块失败: {str(e)}", exc_info=True)
            # 分块失败时，返回整个文本作为单个块
            logger.warning("分块失败，返回整个文本作为单个块")
            return [{
                "text": text,
                "metadata": {
                    **metadata,
                    "chunk_index": 0,
                    "total_chunks": 1,
                }
            }]

    def _smart_chunk_text(self, text: str) -> List[str]:
        """智能分块文本，保持操作流程的完整性.
        
        Args:
            text: 输入文本
            
        Returns:
            分块结果列表
        """
        import re
        
        # 检测操作流程模式
        operation_patterns = [
            r'#### .+?\n.*?步骤1.*?步骤2.*?(?=####|$)',  # 完整的操作流程
            r'### .+?\n.*?步骤1.*?步骤2.*?(?=###|$)',   # 三级标题的操作流程
        ]
        
        # 查找操作流程块
        operation_blocks = []
        remaining_text = text
        
        for pattern in operation_patterns:
            matches = re.finditer(pattern, text, re.DOTALL | re.MULTILINE)
            for match in matches:
                start, end = match.span()
                operation_blocks.append({
                    'start': start,
                    'end': end,
                    'text': match.group(),
                    'type': 'operation_flow'
                })
        
        # 如果找到操作流程，特殊处理
        if operation_blocks:
            logger.info(f"检测到 {len(operation_blocks)} 个操作流程块，使用智能分割")
            logger.debug("=== 操作流程块详情 ===")
            for i, block in enumerate(operation_blocks):
                block_preview = block['text'].replace('\n', '\\n')[:100]
                logger.debug(f"操作块 {i+1}: 位置={block['start']}-{block['end']}, 长度={len(block['text'])}")
                logger.debug(f"  预览: '{block_preview}...'")
            return self._chunk_with_operation_blocks(text, operation_blocks)
        else:
            logger.debug("未检测到操作流程模式，使用标准分割")
            # 没有特殊结构，使用标准分割
            return self.splitter.split_text(text)
    
    def _chunk_with_operation_blocks(self, text: str, operation_blocks: List[Dict]) -> List[str]:
        """处理包含操作流程的文本分块.
        
        Args:
            text: 原始文本
            operation_blocks: 操作流程块列表
            
        Returns:
            分块结果列表
        """
        chunks = []
        last_end = 0
        
        # 按位置排序操作块
        operation_blocks.sort(key=lambda x: x['start'])
        
        logger.debug("=== 操作流程块处理过程 ===")
        
        for i, block in enumerate(operation_blocks):
            # 添加操作块之前的文本
            if block['start'] > last_end:
                before_text = text[last_end:block['start']].strip()
                if before_text:
                    logger.debug(f"处理操作块 {i+1} 之前的文本: 长度={len(before_text)}")
                    # 对前面的文本使用标准分割
                    before_chunks = self.splitter.split_text(before_text)
                    logger.debug(f"  标准分割产生 {len(before_chunks)} 个chunk")
                    for j, chunk in enumerate(before_chunks):
                        logger.debug(f"    前置Chunk {j+1}: 长度={len(chunk)}")
                    chunks.extend(before_chunks)
            
            # 处理操作流程块
            operation_text = block['text']
            logger.debug(f"处理操作流程块 {i+1}: 长度={len(operation_text)}")
            
            if len(operation_text) <= self.chunk_size:
                # 操作流程块不超过大小限制，保持完整
                chunks.append(operation_text)
                logger.debug(f"  ✅ 保持操作流程块完整: {len(operation_text)} 字符")
            else:
                # 操作流程块太大，需要分割，但尽量在步骤边界分割
                logger.debug(f"  ⚠️ 操作流程块过大，需要分割: {len(operation_text)} > {self.chunk_size}")
                operation_chunks = self._split_operation_block(operation_text)
                logger.debug(f"  分割为 {len(operation_chunks)} 个子块")
                for j, chunk in enumerate(operation_chunks):
                    logger.debug(f"    操作子块 {j+1}: 长度={len(chunk)}")
                chunks.extend(operation_chunks)
            
            last_end = block['end']
        
        # 添加最后剩余的文本
        if last_end < len(text):
            remaining_text = text[last_end:].strip()
            if remaining_text:
                logger.debug(f"处理剩余文本: 长度={len(remaining_text)}")
                remaining_chunks = self.splitter.split_text(remaining_text)
                logger.debug(f"  标准分割产生 {len(remaining_chunks)} 个chunk")
                for j, chunk in enumerate(remaining_chunks):
                    logger.debug(f"    剩余Chunk {j+1}: 长度={len(chunk)}")
                chunks.extend(remaining_chunks)
        
        logger.debug(f"操作流程处理完成，总共产生 {len(chunks)} 个chunk")
        return chunks
    
    def _split_operation_block(self, operation_text: str) -> List[str]:
        """分割大的操作流程块，尽量保持步骤完整性.
        
        Args:
            operation_text: 操作流程文本
            
        Returns:
            分块结果列表
        """
        import re
        
        logger.debug("=== 操作流程块分割详情 ===")
        logger.debug(f"原始操作块长度: {len(operation_text)}")
        
        # 尝试在步骤边界分割
        step_pattern = r'\n\*\*步骤\d+[：:][^*]*?(?=\n\*\*步骤\d+[：:]|\n\*\*|$)'
        steps = re.findall(step_pattern, operation_text, re.DOTALL)
        
        logger.debug(f"检测到步骤数量: {len(steps)}")
        for i, step in enumerate(steps):
            step_preview = step.replace('\n', '\\n')[:80]
            logger.debug(f"  步骤 {i+1}: 长度={len(step)}, 预览='{step_preview}...'")
        
        if len(steps) >= 2:
            # 找到多个步骤，尝试组合
            logger.debug("找到多个步骤，按步骤边界分割")
            chunks = []
            current_chunk = ""
            
            # 添加标题部分（步骤之前的内容）
            title_match = re.match(r'^(.*?)(?=\n\*\*步骤)', operation_text, re.DOTALL)
            if title_match:
                title_part = title_match.group(1).strip()
                current_chunk = title_part
                logger.debug(f"标题部分: 长度={len(title_part)}")
            
            for i, step in enumerate(steps):
                step_text = step.strip()
                # 检查添加这个步骤是否会超过大小限制
                combined_length = len(current_chunk + "\n\n" + step_text)
                logger.debug(f"尝试添加步骤 {i+1}: 当前长度={len(current_chunk)}, 步骤长度={len(step_text)}, 合并后={combined_length}")
                
                if combined_length <= self.chunk_size:
                    if current_chunk:
                        current_chunk += "\n\n" + step_text
                    else:
                        current_chunk = step_text
                    logger.debug(f"  ✅ 成功添加步骤 {i+1}，当前chunk长度={len(current_chunk)}")
                else:
                    # 超过限制，保存当前块并开始新块
                    if current_chunk:
                        chunks.append(current_chunk)
                        logger.debug(f"  💾 保存当前chunk: 长度={len(current_chunk)}")
                    current_chunk = step_text
                    logger.debug(f"  🆕 开始新chunk，步骤 {i+1}: 长度={len(step_text)}")
            
            # 添加最后一个块
            if current_chunk:
                chunks.append(current_chunk)
                logger.debug(f"💾 保存最后一个chunk: 长度={len(current_chunk)}")
            
            logger.debug(f"操作流程块按步骤分割为 {len(chunks)} 个块")
            for i, chunk in enumerate(chunks):
                chunk_preview = chunk.replace('\n', '\\n')[:100]
                logger.debug(f"  结果Chunk {i+1}: 长度={len(chunk)}, 预览='{chunk_preview}...'")
            return chunks
        else:
            # 没有找到步骤结构，使用标准分割
            logger.debug("未找到步骤结构，使用标准分割")
            standard_chunks = self.splitter.split_text(operation_text)
            logger.debug(f"标准分割产生 {len(standard_chunks)} 个chunk")
            for i, chunk in enumerate(standard_chunks):
                logger.debug(f"  标准Chunk {i+1}: 长度={len(chunk)}")
            return standard_chunks
