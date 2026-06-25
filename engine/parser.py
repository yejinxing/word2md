"""Semantic Parser — 将 Word XML 解析为 DocumentIR。"""

from .ir import DocumentIR, IRNode, Span, TableCell
from .reader import DocxReader
from xml.etree import ElementTree as ET


class SemanticParser:
    """解析 .docx XML，输出 DocumentIR。"""

    def __init__(self, reader: DocxReader):
        self.reader = reader
        self.doc = reader.document_xml
        self.body = self.doc.find(DocxReader.qn("w:body"))

    def parse(self) -> DocumentIR:
        """完整解析文档，返回 DocumentIR。"""
        ir = DocumentIR()
        ir.title = self._extract_title()
        ir.author = self._extract_author()

        if self.body is None:
            return ir

        for element in self.body:
            tag = element.tag.split("}")[-1] if "}" in element.tag else element.tag

            if tag == "p":
                node = self._parse_paragraph(element)
                if node:
                    ir.nodes.append(node)
            elif tag == "tbl":
                node = self._parse_table(element)
                if node:
                    ir.nodes.append(node)

        return ir

    def _parse_paragraph(self, p_elem: ET.Element) -> IRNode | None:
        """解析单个段落元素，识别标题/段落/页眉页脚。"""
        pPr = p_elem.find(DocxReader.qn("w:pPr"))
        style = ""
        outline_lvl = 0

        if pPr is not None:
            pStyle = pPr.find(DocxReader.qn("w:pStyle"))
            if pStyle is not None:
                style = pStyle.attrib.get(DocxReader.qn("w:val"), "")
            outline = pPr.find(DocxReader.qn("w:outlineLvl"))
            if outline is not None:
                outline_lvl = int(outline.attrib.get(DocxReader.qn("w:val"), "0")) + 1

        # 判断标题
        is_heading = style.startswith("Heading") or outline_lvl > 0
        level = 1
        if is_heading:
            if outline_lvl > 0:
                level = outline_lvl
            elif style.startswith("Heading"):
                try:
                    level = int(style.replace("Heading", ""))
                except ValueError:
                    level = 1
            level = min(max(level, 1), 6)

        # 提取 spans
        spans = self._extract_spans(p_elem)
        text = "".join(s.text for s in spans)

        if not text.strip():
            return None

        # 忽略页眉/页脚
        if "header" in style.lower() or "footer" in style.lower():
            return None

        if is_heading:
            return IRNode(type="heading", level=level, children=spans)

        return IRNode(type="paragraph", children=spans)

    def _extract_spans(self, p_elem: ET.Element) -> list[Span]:
        """提取段落中所有 run 的 inline 格式。"""
        spans = []
        for r_elem in p_elem.findall(DocxReader.qn("w:r")):
            rPr = r_elem.find(DocxReader.qn("w:rPr"))
            bold = italic = underline = False
            highlight = color = None

            if rPr is not None:
                bold = rPr.find(DocxReader.qn("w:b")) is not None
                italic = rPr.find(DocxReader.qn("w:i")) is not None
                underline = rPr.find(DocxReader.qn("w:u")) is not None

                hl = rPr.find(DocxReader.qn("w:highlight"))
                if hl is not None:
                    highlight = hl.attrib.get(DocxReader.qn("w:val"), "yellow")

                clr = rPr.find(DocxReader.qn("w:color"))
                if clr is not None:
                    color = clr.attrib.get(DocxReader.qn("w:val"), None)

            t_elem = r_elem.find(DocxReader.qn("w:t"))
            text = t_elem.text if t_elem is not None and t_elem.text else ""

            spans.append(Span(
                text=text,
                bold=bold,
                italic=italic,
                underline=underline,
                highlight=highlight,
                color=color,
            ))
        return spans

    def _parse_table(self, tbl_elem: ET.Element) -> IRNode | None:
        """解析表格，含 colspan 处理。"""
        rows = []
        for tr in tbl_elem.findall(DocxReader.qn("w:tr")):
            cells = []
            for tc in tr.findall(DocxReader.qn("w:tc")):
                tcPr = tc.find(DocxReader.qn("w:tcPr"))
                colspan = 1
                if tcPr is not None:
                    grid_span = tcPr.find(DocxReader.qn("w:gridSpan"))
                    if grid_span is not None:
                        colspan = int(grid_span.attrib.get(DocxReader.qn("w:val"), "1"))

                paras = tc.findall(DocxReader.qn("w:p"))
                cell_text = ""
                for p in paras:
                    spans = self._extract_spans(p)
                    cell_text += "".join(s.text for s in spans) + "\n"

                cells.append(TableCell(text=cell_text.strip(), colspan=colspan))
            rows.append(cells)
        return IRNode(type="table", children=rows)

    def _extract_title(self) -> str:
        """从 docProps/core.xml 提取标题。"""
        try:
            core = self.reader.zip.read("docProps/core.xml")
            root = ET.fromstring(core)
            ns = "{http://purl.org/dc/elements/1.1/}"
            title = root.find(f"{ns}title")
            return title.text if title is not None and title.text else ""
        except (KeyError, ET.ParseError):
            return ""

    def _extract_author(self) -> str:
        """从 docProps/core.xml 提取作者。"""
        try:
            core = self.reader.zip.read("docProps/core.xml")
            root = ET.fromstring(core)
            ns = "{http://purl.org/dc/elements/1.1/}"
            creator = root.find(f"{ns}creator")
            return creator.text if creator is not None and creator.text else ""
        except (KeyError, ET.ParseError):
            return ""
