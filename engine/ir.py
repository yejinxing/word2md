"""IR (Intermediate Representation) — 文档中间表示 AST。

所有 Word 元素在解析后统一转换为此 IR，Emitter 再根据输出模式
(html/markdown/json) 将 IR 序列化为目标格式。
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Span:
    """文本片段 — 带格式的 inline 元素。"""
    text: str
    bold: bool = False
    italic: bool = False
    underline: bool = False
    strikethrough: bool = False
    highlight: Optional[str] = None       # 高亮颜色 e.g. "yellow"
    color: Optional[str] = None            # 字体颜色 e.g. "#FF0000"
    superscript: bool = False
    subscript: bool = False
    url: Optional[str] = None              # 超链接
    footnote_id: Optional[str] = None      # 脚注 ID


@dataclass
class IRNode:
    """文档节点 — 可以是段落、标题、表格、图片等。"""
    type: str  # "heading" | "paragraph" | "table" | "list" | "image" | "page_break"
    level: int = 0                         # 标题层级 1-6
    children: list = field(default_factory=list)  # list[Span | IRNode]
    attrs: dict = field(default_factory=dict)     # 附加属性


@dataclass
class TableCell:
    """表格单元格"""
    text: str
    rowspan: int = 1
    colspan: int = 1
    spans: list = field(default_factory=list)  # list[Span]


@dataclass
class DocumentIR:
    """完整文档 IR — 转换管道的核心数据结构。"""
    title: str = ""
    author: str = ""
    date: str = ""
    nodes: list = field(default_factory=list)  # list[IRNode]
    images: dict = field(default_factory=dict)  # {image_id: filename}
    footnotes: list = field(default_factory=list)  # list[dict]
