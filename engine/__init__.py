"""Engine — Word (.docx) → HTML/Markdown/JSON 转换管道。支持 .doc 自动转换。"""

import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from .reader import DocxReader
from .parser import SemanticParser
from .ir import DocumentIR
from .emitter import HtmlEmitter, MarkdownEmitter, JsonEmitter

__all__ = [
    "convert",
    "DocxReader",
    "SemanticParser",
    "DocumentIR",
    "HtmlEmitter",
    "MarkdownEmitter",
    "JsonEmitter",
]

EMITTERS = {
    "html": HtmlEmitter,
    "markdown": MarkdownEmitter,
    "json": JsonEmitter,
}


def convert(
    input_path: str | Path,
    output_mode: str = "html",
    extract_images: bool = True,
    images_dir: Optional[str | Path] = None,
    skip_cover: bool = False,
    frontmatter: bool = False,
) -> dict:
    """一站式转换：Reader → Parser → Emitter。

    Returns:
        {
            "content": str | dict,
            "metadata": {"title": str, "author": str},
            "stats": {"headings": int, "paragraphs": int, "tables": int, "images": int},
            "images": list[dict],
        }
    """
    input_path = Path(input_path)

    # .doc → .docx 自动转换（需要 LibreOffice）
    if input_path.suffix.lower() == ".doc":
        try:
            tmp_dir = tempfile.mkdtemp()
            subprocess.run(
                ["soffice", "--headless", "--convert-to", "docx",
                 "--outdir", tmp_dir, str(input_path)],
                check=True, capture_output=True, timeout=60,
            )
            converted = list(Path(tmp_dir).glob("*.docx"))
            if converted:
                input_path = converted[0]
            else:
                raise RuntimeError("LibreOffice .doc→.docx 转换失败")
        except FileNotFoundError:
            raise RuntimeError(
                ".doc 文件需要 LibreOffice 转换。请安装 LibreOffice 或使用 .docx 格式。\n"
                "下载: https://www.libreoffice.org/"
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError("LibreOffice 转换超时（60秒）")

    reader = DocxReader(str(input_path))
    ir = SemanticParser(reader, skip_cover=skip_cover).parse()

    # 提取图片
    image_list = []
    if extract_images:
        if images_dir is None:
            images_dir = input_path.parent / "images"
        else:
            images_dir = Path(images_dir)
        images_dir.mkdir(parents=True, exist_ok=True)

        for node in ir.nodes:
            if node.type == "image":
                r_id = node.attrs.get("rId", "")
                ext = node.attrs.get("ext", ".png")
                filename = node.attrs.get("filename", f"image_{r_id}{ext}")
                save_path = images_dir / filename

                img_bytes = reader.images.get(r_id)
                if img_bytes:
                    save_path.write_bytes(img_bytes)
                    node.attrs["src"] = str(save_path)
                    node.attrs["filename"] = filename
                    image_list.append({
                        "id": r_id,
                        "filename": filename,
                        "path": str(save_path),
                        "size": len(img_bytes),
                    })

    emitter = EMITTERS[output_mode]()
    body = emitter.emit(ir, frontmatter=frontmatter)

    stats = {
        "headings": sum(1 for n in ir.nodes if n.type == "heading"),
        "paragraphs": sum(1 for n in ir.nodes if n.type == "paragraph"),
        "tables": sum(1 for n in ir.nodes if n.type == "table"),
        "images": len(image_list),
    }

    return {
        "content": body,
        "metadata": {"title": ir.title, "author": ir.author},
        "stats": stats,
        "images": image_list,
    }
