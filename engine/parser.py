"""Semantic Parser — 将 Word XML 解析为 DocumentIR。"""

from .ir import DocumentIR, IRNode, Span, TableCell
from .reader import DocxReader
from .numbering import NumberingResolver
from xml.etree import ElementTree as ET


class SemanticParser:
    """解析 .docx XML，输出 DocumentIR。"""

    def __init__(self, reader: DocxReader, skip_cover: bool = True):
        self.reader = reader
        self.doc = reader.document_xml
        self.body = self.doc.find(DocxReader.qn("w:body"))
        self.skip_cover = skip_cover
        self._footnotes_cache: dict | None = None
        self._para_count = 0
        self._cover_ended = not skip_cover
        self._heading_styles: dict = self._load_heading_styles()
        try:
            num_xml = reader.zip.read("word/numbering.xml")
        except KeyError:
            num_xml = None
        self.numbering = NumberingResolver(num_xml)

    def parse(self) -> DocumentIR:
        """完整解析文档，返回 DocumentIR。"""
        ir = DocumentIR()
        ir.title = self._extract_title()
        ir.author = self._extract_author()
        ir.date = self._extract_date()

        if self.body is None:
            return ir

        # 预解析脚注
        self._parse_footnotes(ir)

        for element in self.body:
            tag = element.tag.split("}")[-1] if "}" in element.tag else element.tag

            if tag == "p":
                if self._is_toc(element):
                    continue
                node = self._parse_paragraph(element)
                if node:
                    ir.nodes.append(node)
            elif tag == "tbl":
                node = self._parse_table(element)
                if node:
                    ir.nodes.append(node)

        return ir

    def _parse_paragraph(self, p_elem: ET.Element) -> IRNode | None:
        """解析单个段落元素，识别标题/段落/图片。"""
        image = self._detect_image(p_elem)
        if image:
            return image

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

        is_heading = style in self._heading_styles or outline_lvl > 0
        level = 1
        if is_heading:
            if outline_lvl > 0:
                level = outline_lvl
            elif style in self._heading_styles:
                level = self._heading_styles[style]
            level = min(max(level, 1), 6)

        # 封面页跳过：最多跳过前 10 个段落，或遇到分页符时停止
        if not self._cover_ended:
            self._para_count += 1
            # 检测分页符
            rprs = p_elem.findall(f".//{DocxReader.qn('w:lastRenderedPageBreak')}")
            has_break = len(rprs) > 0
            pPr = p_elem.find(DocxReader.qn('w:pPr'))
            if pPr is not None:
                sect = pPr.find(DocxReader.qn('w:sectPr'))
                if sect is not None:
                    has_break = True
            if has_break or self._para_count > 10 or is_heading:
                self._cover_ended = True
            else:
                return None

        spans = self._extract_spans(p_elem)
        text = "".join(s.text for s in spans)

        # 自动编号前缀
        num_prefix = ""
        if pPr is not None:
            numPr = pPr.find(DocxReader.qn("w:numPr"))
            if numPr is not None:
                numId = numPr.find(DocxReader.qn("w:numId"))
                ilvl = numPr.find(DocxReader.qn("w:ilvl"))
                nid = numId.attrib.get(DocxReader.qn("w:val"), "") if numId is not None else ""
                lvl = int(ilvl.attrib.get(DocxReader.qn("w:val"), "0")) if ilvl is not None else 0
                num_prefix = self.numbering.get_prefix(nid, lvl)

        if not text.strip() and not num_prefix:
            return None

        if "header" in style.lower() or "footer" in style.lower():
            return None

        if is_heading:
            return IRNode(type="heading", level=level, children=spans, attrs={"num_prefix": num_prefix})

        return IRNode(type="paragraph", children=spans, attrs={"num_prefix": num_prefix})

    def _load_heading_styles(self) -> dict:
        """从 styles.xml 加载标题样式 ID → 级别映射。"""
        heading_map = {
            "Heading1": 1, "Heading2": 2, "Heading3": 3,
            "Heading4": 4, "Heading5": 5, "Heading6": 6,
        }
        try:
            styles_root = self.reader.styles_xml
            for style in styles_root.findall(f".//{DocxReader.qn('w:style')}"):
                style_id = style.attrib.get(DocxReader.qn("w:styleId"), "")
                pPr = style.find(DocxReader.qn("w:pPr"))
                if pPr is not None:
                    outline = pPr.find(DocxReader.qn("w:outlineLvl"))
                    if outline is not None:
                        lvl = int(outline.attrib.get(DocxReader.qn("w:val"), "0")) + 1
                        heading_map[style_id] = min(max(lvl, 1), 6)
                based = style.find(DocxReader.qn("w:basedOn"))
                if based is not None:
                    based_val = based.attrib.get(DocxReader.qn("w:val"), "")
                    if based_val in heading_map:
                        heading_map[style_id] = heading_map[based_val]
        except Exception:
            pass
        return heading_map

    def _is_toc(self, p_elem: ET.Element) -> bool:
        """检测段落是否为目录(TOC)内容。仅当同时满足 TOC 样式 + PAGEREF/HYPERLINK 时才跳过。"""
        instr_texts = p_elem.findall(f".//{DocxReader.qn('w:instrText')}")
        has_pageref = False
        for instr in instr_texts:
            if instr.text and ("PAGEREF" in instr.text or "HYPERLINK" in instr.text):
                has_pageref = True
                break
        if not has_pageref:
            return False
        # 同时检查 TOC 样式
        pPr = p_elem.find(DocxReader.qn("w:pPr"))
        if pPr is not None:
            pStyle = pPr.find(DocxReader.qn("w:pStyle"))
            if pStyle is not None:
                style = pStyle.attrib.get(DocxReader.qn("w:val"), "")
                if "toc" in style.lower():
                    return True
        return False

    def _extract_spans(self, p_elem: ET.Element) -> list[Span]:
        """提取段落中所有 run 的 inline 格式，含域代码和脚注引用。"""
        spans = []
        in_field = False
        field_text = ""

        for r_elem in p_elem.findall(DocxReader.qn("w:r")):
            rPr = r_elem.find(DocxReader.qn("w:rPr"))
            bold = italic = underline = False
            highlight = color = None
            footnote_id = None

            # 检测域代码
            fld_char = r_elem.find(DocxReader.qn("w:fldChar"))
            instr_text = r_elem.find(DocxReader.qn("w:instrText"))

            if fld_char is not None:
                fld_type = fld_char.attrib.get(DocxReader.qn("w:fldCharType"), "")
                if fld_type == "begin":
                    in_field = True
                    field_text = ""
                    continue
                elif fld_type == "end":
                    in_field = False
                    field_text = ""
                    continue
            if instr_text is not None and instr_text.text:
                field_text = instr_text.text
                continue
            if in_field:
                continue  # 跳过域代码之间的内容

            # 检测脚注引用
            footnote_ref = r_elem.find(DocxReader.qn("w:footnoteReference"))
            if footnote_ref is not None:
                footnote_id = footnote_ref.attrib.get(DocxReader.qn("w:id"), "")

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

            # 检测 Wingdings 勾选框符号
            sym_elem = r_elem.find(DocxReader.qn("w:sym"))
            if sym_elem is not None:
                char_code = sym_elem.attrib.get(DocxReader.qn("w:char"), "")
                font = sym_elem.attrib.get(DocxReader.qn("w:font"), "").lower()
                if "wingdings" in font:
                    if char_code in ("00A8", "00A3", "0075"):
                        text = "☐"
                    elif char_code in ("00FE", "00FC"):
                        text = "☑"

            if text or highlight or color or footnote_id:
                spans.append(Span(
                    text=text,
                    bold=bold,
                    italic=italic,
                    underline=underline,
                    highlight=highlight,
                    color=color,
                    footnote_id=footnote_id,
                ))
        return spans

    def _parse_table(self, tbl_elem: ET.Element) -> IRNode | None:
        """解析表格，含 colspan、grid 列宽、单元格自动编号、空列补齐。"""
        # 读取 tblGrid 列宽
        tbl_grid = tbl_elem.find(DocxReader.qn("w:tblGrid"))
        grid_widths = []
        if tbl_grid is not None:
            for gc in tbl_grid.findall(DocxReader.qn("w:gridCol")):
                w = gc.attrib.get(DocxReader.qn("w:w"), "0")
                grid_widths.append(int(w) if w.isdigit() else 0)

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
                # 逐个段落提取 spans，含自动编号
                paras = tc.findall(DocxReader.qn("w:p"))
                cell_paragraphs = []
                for p in paras:
                    spans = self._extract_spans(p)
                    # 检测单元格段落中的自动编号
                    pPr = p.find(DocxReader.qn("w:pPr"))
                    if pPr is not None:
                        numPr = pPr.find(DocxReader.qn("w:numPr"))
                        if numPr is not None:
                            numId = numPr.find(DocxReader.qn("w:numId"))
                            ilvl = numPr.find(DocxReader.qn("w:ilvl"))
                            nid = numId.attrib.get(DocxReader.qn("w:val"), "") if numId is not None else ""
                            lvl = int(ilvl.attrib.get(DocxReader.qn("w:val"), "0")) if ilvl is not None else 0
                            if nid:
                                prefix = self.numbering.get_prefix(nid, lvl)
                                if prefix:
                                    spans.insert(0, Span(text=prefix))
                    if spans:
                        cell_paragraphs.append(spans)
                cells.append(TableCell(colspan=colspan, paragraphs=cell_paragraphs))
            # 对齐到 grid 列数：优先扩展第一格 colspan，保持一致分割线
            if grid_widths and cells:
                row_span = sum(c.colspan for c in cells)
                missing = len(grid_widths) - row_span
                if missing > 0:
                    cells[0].colspan += missing
            rows.append(cells)

        return IRNode(type="table", children=rows,
                      attrs={"grid_widths": grid_widths})

    def _detect_image(self, p_elem: ET.Element) -> IRNode | None:
        """检测段落中的图片 (w:drawing → blip 嵌入)。"""
        drawing = p_elem.find(DocxReader.qn("w:r"))
        if drawing is None:
            return None
        blips = p_elem.findall(f".//{DocxReader.qn('a:blip')}")
        if not blips:
            return None
        blip = blips[0]
        embed = blip.attrib.get(f"{{{DocxReader.NS['r']}}}embed", "")
        if not embed:
            return None
        ext = self.reader.get_image_ext(embed)
        return IRNode(
            type="image",
            attrs={"rId": embed, "ext": ext, "filename": f"image_{embed}{ext}"},
        )

    def _parse_footnotes(self, ir: DocumentIR):
        """解析脚注/尾注。"""
        try:
            fns_xml = self.reader.zip.read("word/footnotes.xml")
        except KeyError:
            return
        root = ET.fromstring(fns_xml)
        ns = DocxReader.qn("w:footnote")
        for fn in root.findall(ns):
            fn_id = fn.attrib.get(DocxReader.qn("w:id"), "")
            if fn_id in ("0", "-1"):
                continue
            text_parts = []
            for p in fn.findall(DocxReader.qn("w:p")):
                for t in p.findall(f".//{DocxReader.qn('w:t')}"):
                    if t.text:
                        text_parts.append(t.text)
            ir.footnotes.append({
                "id": fn_id,
                "text": "".join(text_parts),
            })

    def _extract_title(self) -> str:
        try:
            core = self.reader.zip.read("docProps/core.xml")
            root = ET.fromstring(core)
            ns = "{http://purl.org/dc/elements/1.1/}"
            title = root.find(f"{ns}title")
            return title.text if title is not None and title.text else ""
        except (KeyError, ET.ParseError):
            return ""

    def _extract_author(self) -> str:
        try:
            core = self.reader.zip.read("docProps/core.xml")
            root = ET.fromstring(core)
            ns = "{http://purl.org/dc/elements/1.1/}"
            creator = root.find(f"{ns}creator")
            return creator.text if creator is not None and creator.text else ""
        except (KeyError, ET.ParseError):
            return ""

    def _extract_date(self) -> str:
        """提取文档日期。"""
        try:
            core = self.reader.zip.read("docProps/core.xml")
            root = ET.fromstring(core)
            ns = "{http://purl.org/dc/terms/}"
            d = root.find(f"{ns}created")
            return d.text[:10] if d is not None and d.text else ""
        except (KeyError, ET.ParseError):
            return ""
