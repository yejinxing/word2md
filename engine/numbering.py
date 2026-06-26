"""NumberingResolver — 解析 Word 自动编号（numbering.xml）。

支持 decimal / chineseCounting / upperRoman / lowerLetter / upperLetter
等多级编号格式，自动跟踪计数器状态。
"""

from xml.etree import ElementTree as ET

CN_DIGITS = ["", "一", "二", "三", "四", "五", "六", "七", "八", "九", "十"]


def _to_chinese_number(n: int) -> str:
    if n <= 0:
        return "〇"
    if n <= 10:
        return CN_DIGITS[n]
    if n < 20:
        return f"十{CN_DIGITS[n % 10]}" if n % 10 else "十"
    return str(n)


def _resolve_format(fmt: str, counter: int) -> str:
    if fmt in ("chineseCounting", "chineseCountingThousand"):
        return _to_chinese_number(counter)
    elif fmt == "upperRoman":
        m = {1: "Ⅰ", 2: "Ⅱ", 3: "Ⅲ", 4: "Ⅳ", 5: "Ⅴ", 6: "Ⅵ", 7: "Ⅶ", 8: "Ⅷ", 9: "Ⅸ", 10: "Ⅹ"}
        return m.get(counter, str(counter))
    elif fmt == "lowerRoman":
        m = {1: "ⅰ", 2: "ⅱ", 3: "ⅲ", 4: "ⅳ", 5: "ⅴ", 6: "ⅵ", 7: "ⅶ", 8: "ⅷ", 9: "ⅸ", 10: "ⅹ"}
        return m.get(counter, str(counter))
    elif fmt == "upperLetter":
        return chr(64 + counter) if 1 <= counter <= 26 else str(counter)
    elif fmt == "lowerLetter":
        return chr(96 + counter) if 1 <= counter <= 26 else str(counter)
    else:
        return str(counter)


class NumberingResolver:
    """解析 numbering.xml，追踪编号计数器。"""

    W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

    def __init__(self, numbering_xml: bytes | None):
        self._level_fmts: dict = {}  # (numId, ilvl) → {"fmt":str, "template":str}
        self._counters: dict = {}    # (numId, ilvl) → int
        if numbering_xml:
            self._parse(ET.fromstring(numbering_xml))

    def _parse(self, root: ET.Element):
        w = self.W
        abs_map: dict = {}
        for absnum in root.findall(f"{{{w}}}abstractNum"):
            abs_id = absnum.attrib.get(f"{{{w}}}abstractNumId", "")
            abs_map[abs_id] = {}
            for lvl in absnum.findall(f"{{{w}}}lvl"):
                ilvl = int(lvl.attrib.get(f"{{{w}}}ilvl", "0"))
                fmt = "decimal"
                nf = lvl.find(f"{{{w}}}numFmt")
                if nf is not None:
                    fmt = nf.attrib.get(f"{{{w}}}val", "decimal")
                lt = lvl.find(f"{{{w}}}lvlText")
                template = lt.attrib.get(f"{{{w}}}val", "%1.") if lt is not None else "%1."
                abs_map[abs_id][ilvl] = {"fmt": fmt, "template": template}

        for num in root.findall(f"{{{w}}}num"):
            num_id = num.attrib.get(f"{{{w}}}numId", "")
            abs_ref = num.find(f"{{{w}}}abstractNumId")
            if abs_ref is not None:
                abs_id = abs_ref.attrib.get(f"{{{w}}}val", "")
                if abs_id in abs_map:
                    for ilvl, info in abs_map[abs_id].items():
                        self._level_fmts[(num_id, ilvl)] = info

    def get_prefix(self, num_id: str, ilvl: int) -> str:
        """生成编号前缀并推进计数器。"""
        if not num_id:
            return ""
        key = (num_id, ilvl)
        if key not in self._level_fmts:
            return ""

        self._counters[key] = self._counters.get(key, 0) + 1
        counter = self._counters[key]

        # 重置更深层计数器
        for (nid, lvl) in list(self._counters.keys()):
            if nid == num_id and lvl > ilvl:
                self._counters[(nid, lvl)] = 0

        info = self._level_fmts[key]
        rendered = _resolve_format(info["fmt"], counter)

        # 多级编号拼接
        template = info["template"]
        if "." in template and template.count("%") > 1:
            parts = []
            for l in range(ilvl + 1):
                pk = (num_id, l)
                if pk in self._level_fmts:
                    pc = self._counters.get(pk, 1) or 1
                    parts.append(_resolve_format(self._level_fmts[pk]["fmt"], pc))
            rendered = ".".join(parts)

        # 从模板提取前后缀（支持中文模板如 第%1章、(一)、%1、）
        import re
        parts = re.split(r"%\d+", template, maxsplit=1)
        prefix = parts[0] if len(parts) > 0 else ""
        suffix = parts[1] if len(parts) > 1 else ""

        return f"{prefix}{rendered}{suffix} "
