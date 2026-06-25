"""Emitter — 将 DocumentIR 序列化为 HTML/Markdown/JSON。"""

from .ir import DocumentIR, IRNode, Span, TableCell
import yaml


def _build_frontmatter(ir: DocumentIR) -> str:
    """生成 YAML frontmatter。"""
    if not any([ir.title, ir.author, ir.date]):
        return ""
    data = {}
    if ir.title:
        data["title"] = ir.title
    if ir.author:
        data["author"] = ir.author
    if ir.date:
        data["date"] = ir.date
    return "---\n" + yaml.dump(data, allow_unicode=True, default_flow_style=False).strip() + "\n---\n"


class HtmlEmitter:
    """输出语义 HTML（默认）。"""

    def emit(self, ir: DocumentIR, frontmatter: bool = True) -> str:
        parts = []
        parts.append(
            "<style>\n"
            "table { border-collapse: collapse; width: 100%; margin: 1em 0; }\n"
            "td, th { border: 1px solid #333; padding: 6px 10px; text-align: left; }\n"
            ".footnotes { font-size: 0.9em; color: #666; }\n"
            "</style>"
        )
        if frontmatter:
            fm = _build_frontmatter(ir)
            if fm:
                parts.append("<!--\n" + fm.strip("-") + "-->")
        for node in ir.nodes:
            rendered = self._render_node(node)
            if rendered:
                parts.append(rendered)
        if ir.footnotes:
            parts.append(self._render_footnotes(ir))
        return "\n".join(parts)

    def _render_node(self, node: IRNode) -> str:
        if node.type == "heading":
            level = min(max(node.level, 1), 6)
            return f"<h{level}>{self._render_spans(node.children)}</h{level}>"

        elif node.type == "paragraph":
            return f"<p>{self._render_spans(node.children)}</p>"

        elif node.type == "table":
            return self._render_table(node.children)

        elif node.type == "image":
            alt = node.attrs.get("alt", "")
            src = node.attrs.get("src", "")
            return f'<img src="{src}" alt="{alt}">'

        return ""

    def _render_spans(self, spans: list) -> str:
        result = []
        for span in spans:
            if not isinstance(span, Span):
                continue
            text = span.text or ""

            # 空下划线 → &nbsp; 占位
            if span.underline and not text.strip():
                text = "&nbsp;" * 10

            if span.url:
                text = f'<a href="{span.url}">{text}</a>'
            if span.color:
                text = f'<span style="color:{span.color}">{text}</span>'
            if span.highlight:
                text = f"<mark>{text}</mark>"
            if span.strikethrough:
                text = f"<del>{text}</del>"
            if span.underline:
                text = f"<u>{text}</u>"
            if span.bold:
                text = f"<strong>{text}</strong>"
            if span.italic:
                text = f"<em>{text}</em>"
            if span.footnote_id:
                text = f'<sup><a href="#fn{span.footnote_id}" id="fnref{span.footnote_id}">[{span.footnote_id}]</a></sup>'
            if span.superscript:
                text = f"<sup>{text}</sup>"
            if span.subscript:
                text = f"<sub>{text}</sub>"

            result.append(text)
        return "".join(result)

    def _render_footnotes(self, ir: DocumentIR) -> str:
        """渲染脚注区。"""
        lines = ['<hr>', '<div class="footnotes">']
        for fn in ir.footnotes:
            lines.append(
                f'<p id="fn{fn["id"]}"><sup><a href="#fnref{fn["id"]}">[{fn["id"]}]</a></sup> {fn["text"]}</p>'
            )
        lines.append("</div>")
        return "\n".join(lines)

    def _render_table(self, rows: list) -> str:
        if not rows:
            return ""
        lines = ["<table>"]
        for row in rows:
            cells_html = []
            for cell in row:
                if not isinstance(cell, TableCell):
                    continue
                attrs = ""
                if cell.colspan > 1:
                    attrs += f' colspan="{cell.colspan}"'
                if cell.rowspan > 1:
                    attrs += f' rowspan="{cell.rowspan}"'
                cell_text = cell.text if cell.text else "&nbsp;"
                cells_html.append(f"<td{attrs}>{cell_text}</td>")
        lines.append("</table>")
        return "\n".join(lines)


class MarkdownEmitter:
    """输出 GFM Markdown。"""

    def emit(self, ir: DocumentIR, frontmatter: bool = True) -> str:
        parts = []
        if frontmatter:
            fm = _build_frontmatter(ir)
            if fm:
                parts.append(fm)
        for node in ir.nodes:
            rendered = self._render_node(node)
            if rendered:
                parts.append(rendered)
        return "\n\n".join(parts)

    def _render_node(self, node: IRNode) -> str:
        if node.type == "heading":
            prefix = "#" * min(max(node.level, 1), 6)
            return f"{prefix} {self._render_spans(node.children)}"

        elif node.type == "paragraph":
            return self._render_spans(node.children)

        elif node.type == "table":
            return self._render_table(node.children)

        return ""

    def _render_spans(self, spans: list) -> str:
        result = []
        for span in spans:
            if not isinstance(span, Span):
                continue
            text = span.text or ""
            if span.url:
                text = f"[{text}]({span.url})"
            if span.strikethrough:
                text = f"~~{text}~~"
            if span.bold:
                text = f"**{text}**"
            if span.italic:
                text = f"*{text}*"
            if span.underline:
                text = f"<u>{text}</u>"
            if span.highlight:
                text = f"<mark>{text}</mark>"
            if span.color:
                text = f'<span style="color:{span.color}">{text}</span>'
            result.append(text)
        return "".join(result)

    def _render_table(self, rows: list) -> str:
        if not rows:
            return ""
        lines = []
        for i, row in enumerate(rows):
            cells = [c.text.replace("|", "\\|") if isinstance(c, TableCell) else ""
                     for c in row]
            lines.append("| " + " | ".join(cells) + " |")
            if i == 0:
                lines.append("| " + " | ".join("---" for _ in cells) + " |")
        return "\n".join(lines)


class JsonEmitter:
    """输出结构化 JSON IR。"""

    def emit(self, ir: DocumentIR, frontmatter: bool = True) -> dict:
        return {
            "title": ir.title,
            "author": ir.author,
            "date": ir.date,
            "nodes": [self._render_node(n) for n in ir.nodes],
            "footnotes": ir.footnotes,
            "stats": self._compute_stats(ir),
        }

    def _render_node(self, node: IRNode) -> dict:
        obj = {"type": node.type}
        if node.level:
            obj["level"] = node.level
        if node.type == "table" and node.children:
            obj["rows"] = [
                [{"text": c.text, "colspan": c.colspan} for c in row if isinstance(c, TableCell)]
                for row in node.children
            ]
        else:
            obj["spans"] = [
                self._render_span(s) for s in node.children if isinstance(s, Span)
            ]
        obj.update(node.attrs)
        return obj

    def _render_span(self, span: Span) -> dict:
        d = {"text": span.text}
        for attr in ("bold", "italic", "underline", "strikethrough", "highlight", "color"):
            val = getattr(span, attr)
            if val:
                d[attr] = val
        return d

    def _compute_stats(self, ir: DocumentIR) -> dict:
        """计算文档统计信息。"""
        stats = {"headings": 0, "paragraphs": 0, "tables": 0}
        for node in ir.nodes:
            if node.type == "heading":
                stats["headings"] += 1
            elif node.type == "paragraph":
                stats["paragraphs"] += 1
            elif node.type == "table":
                stats["tables"] += 1
        return stats
