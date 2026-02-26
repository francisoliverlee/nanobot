"""Text chunking for long documents."""

import logging
from typing import Any, Dict, List

from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger("nanobot.knowledge.text_chunker")


class TextChunker:
    """文本分块器，将长文本分割为语义块."""

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        """初始化分块器.
        
        Args:
            chunk_size: 块大小（字符数）
            chunk_overlap: 块重叠大小（字符数）
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.splitter = None
        self._init_splitter()

    def _init_splitter(self) -> None:
        """初始化文本分割器，配置中文友好的分隔符."""
        # 使用递归字符分割策略，优先在段落、句子边界处分块
        # 分隔符按优先级排序：段落 > 句子 > 标点 > 空格 > 字符
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=[
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
            ],
            keep_separator=True,  # 保留分隔符
            length_function=len,
        )
        logger.info(
            f"文本分块器初始化完成: chunk_size={self.chunk_size}, "
            f"chunk_overlap={self.chunk_overlap}"
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

        # 使用 LangChain 分割文本
        try:
            chunks = self.splitter.split_text(text)
            logger.info(f"文本分块完成: 原始长度={len(text)}, 分块数={len(chunks)}")

            # 为每个分块添加元数据
            result = []
            for i, chunk in enumerate(chunks):
                result.append({
                    "text": chunk,
                    "metadata": {
                        **metadata,  # 保留原始元数据
                        "chunk_index": i,
                        "total_chunks": len(chunks),
                    }
                })

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
