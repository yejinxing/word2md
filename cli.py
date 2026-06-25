"""CLI — word2md 命令行入口。"""

import argparse
import sys
from pathlib import Path
from engine import DocxReader, SemanticParser, HtmlEmitter, MarkdownEmitter, JsonEmitter

EMITTERS = {
    "html": (HtmlEmitter(), ".html"),
    "markdown": (MarkdownEmitter(), ".md"),
    "json": (JsonEmitter(), ".json"),
}


def main():
    parser = argparse.ArgumentParser(prog="word2md", description="Word (.docx) 转 HTML/MD/JSON")
    parser.add_argument("input", type=str, help="输入 .docx 文件")
    parser.add_argument("-o", "--output", type=str, default=None, help="输出文件路径")
    parser.add_argument("--mode", type=str, default="html",
                        choices=["html", "markdown", "json"], help="输出格式 (默认: html)")
    parser.add_argument("--stdout", action="store_true", help="输出到标准输出")

    args = parser.parse_args()
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"错误: 文件不存在 — {args.input}", file=sys.stderr)
        sys.exit(1)

    reader = DocxReader(str(input_path))
    ir = SemanticParser(reader).parse()
    emitter, ext = EMITTERS[args.mode]

    if args.mode == "json":
        import json
        result = json.dumps(emitter.emit(ir), ensure_ascii=False, indent=2)
    else:
        result = emitter.emit(ir)

    if args.stdout:
        print(result)
    else:
        output_path = Path(args.output or input_path.with_suffix(ext))
        output_path.write_text(result, encoding="utf-8")
        print(f"转换完成: {input_path} → {output_path}")


if __name__ == "__main__":
    main()
