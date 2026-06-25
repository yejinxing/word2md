"""DOCX Reader — 读取 .docx 文件，提取原始 XML 数据。"""

from zipfile import ZipFile
from pathlib import Path
from typing import BinaryIO, Union
from xml.etree import ElementTree as ET


class DocxReader:
    """读取 .docx 文件并暴露关键 XML 文档。"""

    NS = {
        "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
        "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
        "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
        "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
        "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
    }

    def __init__(self, source: Union[str, Path, bytes, BinaryIO]):
        self.zip = ZipFile(source) if not isinstance(source, ZipFile) else source
        self._rels = {}
        self._load_rels()

    def _load_rels(self):
        """加载 .rels 关系文件。"""
        try:
            rels_xml = self.zip.read("word/_rels/document.xml.rels")
            root = ET.fromstring(rels_xml)
            for rel in root:
                r_id = rel.attrib.get("Id", "")
                target = rel.attrib.get("Target", "")
                r_type = rel.attrib.get("Type", "")
                self._rels[r_id] = {"target": target, "type": r_type}
        except KeyError:
            pass

    @property
    def document_xml(self) -> ET.Element:
        """document.xml — 正文内容。"""
        return ET.fromstring(self.zip.read("word/document.xml"))

    @property
    def styles_xml(self) -> ET.Element:
        """styles.xml — 样式定义。"""
        return ET.fromstring(self.zip.read("word/styles.xml"))

    @property
    def numbering_xml(self) -> ET.Element:
        """numbering.xml — 编号/列表定义。"""
        return ET.fromstring(self.zip.read("word/numbering.xml"))

    @property
    def footnotes_xml(self) -> ET.Element:
        """footnotes.xml — 脚注。"""
        return ET.fromstring(self.zip.read("word/footnotes.xml"))

    @property
    def images(self) -> dict:
        """返回 {rId: image_bytes} 映射。"""
        imgs = {}
        for r_id, rel in self._rels.items():
            if "image" in rel.get("type", ""):
                try:
                    imgs[r_id] = self.zip.read(f"word/{rel['target']}")
                except KeyError:
                    pass
        return imgs

    def get_image_ext(self, r_id: str) -> str:
        """获取图片文件扩展名。"""
        rel = self._rels.get(r_id, {})
        target = rel.get("target", ".png")
        return Path(target).suffix or ".png"

    @staticmethod
    def qn(tag: str) -> str:
        """生成带命名空间的 XML 标签，如 w:p → {ns}body。"""
        prefix, _, local = tag.partition(":")
        ns = DocxReader.NS.get(prefix, "")
        return f"{{{ns}}}{local}" if ns else local
