"""Emitter — 将 DocumentIR 序列化为 HTML/Markdown/JSON。"""

from .ir import DocumentIR, IRNode, Span, TableCell
import yaml


def _merge_spans(spans: list) -> list:
    """合并相邻同格式 Span。"""
    if not spans: return []
    merged = []
    for s in spans:
        if not isinstance(s, Span): merged.append(s); continue
        if merged and isinstance(merged[-1], Span):
            p = merged[-1]
            if (p.bold == s.bold and p.italic == s.italic and
                p.underline == s.underline and p.strikethrough == s.strikethrough and
                p.highlight == s.highlight and p.color == s.color and
                p.url == s.url and p.footnote_id == s.footnote_id):
                p.text += s.text; continue
        merged.append(s)
    return merged


def _merge_spans(spans: list) -> list:
    """合并相邻同格式 Span。"""
    if not spans: return []
    merged = []
    for s in spans:
        if not isinstance(s, Span):
            merged.append(s); continue
        if merged and isinstance(merged[-1], Span):
            p = merged[-1]
            if (p.bold == s.bold and p.italic == s.italic and
                p.underline == s.underline and p.strikethrough == s.strikethrough and
                p.highlight == s.highlight and p.color == s.color and
                p.url == s.url and p.footnote_id == s.footnote_id):
                p.text += s.text; continue
        merged.append(s)
    return merged


def _build_frontmatter(ir: DocumentIR) -> str:
    if not any([ir.title, ir.author, ir.date]):
        return ""
    data = {}
    if ir.title: data["title"] = ir.title
    if ir.author: data["author"] = ir.author
    if ir.date: data["date"] = ir.date
    return "---\n" + yaml.dump(data, allow_unicode=True, default_flow_style=False).strip() + "\n---\n"


class HtmlEmitter:
    """输出语义 HTML（默认）。"""

    @staticmethod
    def render_spans(spans: list) -> str:
        result = []
        for span in _merge_spans(spans):
            if not isinstance(span, Span): continue
            if not span.text.strip() and not span.underline: continue
            text = span.text or ""
            if span.underline and not text.strip():
                text = "&nbsp;" * 10
            # 下划线占位符（"____" "****" 等纯符号文本）→ 替换为 &nbsp;
            if span.underline and text.strip() and all(c in ' _*●▲▼■□○●☆★' for c in text.strip()):
                text = text.strip().replace(' ', '').replace('_', '').replace('*', '')
                text = "&nbsp;" * max(len(text), 10) if text else "&nbsp;" * 10
            if span.url: text = f'<a href="{span.url}">{text}</a>'
            if span.color: text = f'<span style="color:{span.color}">{text}</span>'
            if span.highlight: text = f"<mark>{text}</mark>"
            if span.strikethrough: text = f"<del>{text}</del>"
            if span.underline: text = f"<u>{text}</u>"
            if span.bold: text = f"<strong>{text}</strong>"
            if span.italic: text = f"<em>{text}</em>"
            if span.footnote_id: text = f'<sup><a href="#fn{span.footnote_id}" id="fnref{span.footnote_id}">[{span.footnote_id}]</a></sup>'
            if span.superscript: text = f"<sup>{text}</sup>"
            if span.subscript: text = f"<sub>{text}</sub>"
            result.append(text)
        return "".join(result)

    @staticmethod
    def render_table(rows: list, grid_widths: list = None) -> str:
        if not rows: return ""
        lines = ["<table>"]
        if grid_widths:
            total = sum(grid_widths)
            if total > 0:
                lines.append("<colgroup>")
                for w in grid_widths:
                    lines.append(f'<col style="width:{w/total*100:.1f}%">')
                lines.append("</colgroup>")
        for row in rows:
            cells_html = []
            for cell in row:
                if not isinstance(cell, TableCell): continue
                attrs = ""
                if cell.colspan > 1: attrs += f' colspan="{cell.colspan}"'
                if cell.rowspan > 1: attrs += f' rowspan="{cell.rowspan}"'
                para_htmls = []
                for ps in cell.paragraphs:
                    filtered = [s for s in ps if isinstance(s, Span)]
                    if filtered: para_htmls.append(HtmlEmitter.render_spans(filtered))
                text = "<br>".join(para_htmls) if para_htmls else "&nbsp;"
                cells_html.append(f"<td{attrs}>{text}</td>")
            lines.append(f"<tr>{''.join(cells_html)}</tr>")
        lines.append("</table>")
        return "\n".join(lines)

    def emit(self, ir: DocumentIR, frontmatter: bool = True) -> str:
        parts = [
            "<style>\n"
            "table { border-collapse: collapse; width: 100%; margin: 1em 0; }\n"
            "td, th { border: 1px solid #333; padding: 6px 10px; text-align: left; }\n"
            ".footnotes { font-size: 0.9em; color: #666; }\n"
            "</style>"
        ]
        if frontmatter:
            fm = _build_frontmatter(ir)
            if fm: parts.append("<!--\n" + fm.strip("-") + "-->")
        for node in ir.nodes:
            rendered = self._render_node(node)
            if rendered: parts.append(rendered)
        if ir.footnotes:
            parts.append(self._render_footnotes(ir))
        return "\n".join(parts)

    def _render_node(self, node: IRNode) -> str:
        if node.type == "heading":
            lvl = min(max(node.level, 1), 6)
            return f"<h{lvl}>{node.attrs.get('num_prefix','')}{self.render_spans(node.children)}</h{lvl}>"
        elif node.type == "paragraph":
            return f"<p>{node.attrs.get('num_prefix','')}{self.render_spans(node.children)}</p>"
        elif node.type == "table":
            return HtmlEmitter.render_table(node.children, node.attrs.get("grid_widths"))
        elif node.type == "image":
            return f'<img src="{node.attrs.get("src","")}" alt="{node.attrs.get("alt","")}">'
        return ""

    def _render_footnotes(self, ir: DocumentIR) -> str:
        lines = ['<hr>', '<div class="footnotes">']
        for fn in ir.footnotes:
            lines.append(f'<p id="fn{fn["id"]}"><sup><a href="#fnref{fn["id"]}">[{fn["id"]}]</a></sup> {fn["text"]}</p>')
        lines.append("</div>")
        return "\n".join(lines)


class MarkdownEmitter:
    """输出 GFM Markdown。合并单元格用 HTML 表格。"""

    def emit(self, ir: DocumentIR, frontmatter: bool = True) -> str:
        parts = []
        if frontmatter:
            fm = _build_frontmatter(ir)
            if fm: parts.append(fm)
        for node in ir.nodes:
            rendered = self._render_node(node)
            if rendered: parts.append(rendered)
        return "\n\n".join(parts)

    def _render_node(self, node: IRNode) -> str:
        if node.type == "heading":
            pfx = "#" * min(max(node.level, 1), 6)
            return f"{pfx} {node.attrs.get('num_prefix','')}{self._render_spans(node.children)}"
        elif node.type == "paragraph":
            return f"{node.attrs.get('num_prefix','')}{self._render_spans(node.children)}"
        elif node.type == "table":
            has = any(c.colspan > 1 or c.rowspan > 1 or len(c.paragraphs) > 1
                      for row in node.children for c in row if isinstance(c, TableCell))
            if has:
                return HtmlEmitter.render_table(node.children)
            return self._render_table_md(node.children)
        return ""

    @staticmethod
    def _merge_spans(spans: list) -> list:
        """合并相邻同格式 Span，避免 **签****订** 碎片。"""
        if not spans: return []
        merged = []
        for s in spans:
            if not isinstance(s, Span):
                merged.append(s)
                continue
            if merged and isinstance(merged[-1], Span):
                prev = merged[-1]
                if (prev.bold == s.bold and prev.italic == s.italic and
                    prev.underline == s.underline and prev.strikethrough == s.strikethrough and
                    prev.highlight == s.highlight and prev.color == s.color and
                    prev.url == s.url and prev.footnote_id == s.footnote_id):
                    prev.text += s.text
                    continue
            merged.append(s)
        return merged

    def _render_spans(self, spans: list) -> str:
        result = []
        for span in _merge_spans(spans):
            if not isinstance(span, Span): continue
            if not span.text.strip() and not span.underline: continue
            text = span.text
            if span.url: text = f"[{text}]({span.url})"
            if span.strikethrough: text = f"~~{text}~~"
            if span.bold: text = f"**{text}**"
            if span.italic: text = f"*{text}*"
            if span.underline: text = f"<u>{text}</u>"
            if span.highlight: text = f"<mark>{text}</mark>"
            if span.color: text = f'<span style="color:{span.color}">{text}</span>'
            result.append(text)
        return "".join(result)

    def _render_table_md(self, rows: list) -> str:
        if not rows: return ""
        lines = []
        for i, row in enumerate(rows):
            cells = []
            for c in row:
                if isinstance(c, TableCell):
                    parts = []
                    for ps in c.paragraphs:
                        parts.append(self._render_spans(ps))
                    ct = "<br>".join(parts).replace("|", "\\|") if parts else ""
                else:
                    ct = ""
                cells.append(ct)
            lines.append("| " + " | ".join(cells) + " |")
            if i == 0:
                lines.append("| " + " | ".join("---" for _ in cells) + " |")
        return "\n".join(lines)


class JsonEmitter:
    """输出结构化 JSON IR。"""

    def emit(self, ir: DocumentIR, frontmatter: bool = True) -> dict:
        return {
            "title": ir.title, "author": ir.author, "date": ir.date,
            "nodes": [self._render_node(n) for n in ir.nodes],
            "footnotes": ir.footnotes,
            "stats": self._compute_stats(ir),
        }

    def _render_node(self, node: IRNode) -> dict:
        obj = {"type": node.type}
        if node.level: obj["level"] = node.level
        if node.type == "table" and node.children:
            obj["rows"] = [
                [{"paragraphs": [[self._render_span(s) for s in p] for p in c.paragraphs],
                  "colspan": c.colspan, "rowspan": c.rowspan}
                 for c in row if isinstance(c, TableCell)]
                for row in node.children
            ]
        else:
            obj["spans"] = [self._render_span(s) for s in node.children if isinstance(s, Span)]
        obj.update(node.attrs)
        return obj

    def _render_span(self, span: Span) -> dict:
        d = {"text": span.text}
        for attr in ("bold","italic","underline","strikethrough","highlight","color","footnote_id"):
            val = getattr(span, attr)
            if val: d[attr] = val
        return d

    def _compute_stats(self, ir: DocumentIR) -> dict:
        stats = {"headings": 0, "paragraphs": 0, "tables": 0}
        for node in ir.nodes:
            if node.type == "heading": stats["headings"] += 1
            elif node.type == "paragraph": stats["paragraphs"] += 1
            elif node.type == "table": stats["tables"] += 1
        return stats
