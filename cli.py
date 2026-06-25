"""CLI — word2md 命令行入口。"""

import argparse
import sys
from pathlib import Path
from engine import convert


def main():
    parser = argparse.ArgumentParser(prog="word2md", description="Word (.docx) 转 HTML/MD/JSON")
    parser.add_argument("input", type=str, help="输入 .docx 文件")
    parser.add_argument("-o", "--output", type=str, default=None, help="输出文件路径")
    parser.add_argument("--mode", type=str, default="html",
                        choices=["html", "markdown", "json"], help="输出格式 (默认: html)")
    parser.add_argument("--no-images", action="store_true", help="不提取图片")
    parser.add_argument("--images-dir", type=str, default=None, help="图片输出目录")
    parser.add_argument("--no-skip-cover", action="store_true", help="保留封面页（默认跳过）")
    parser.add_argument("--no-frontmatter", action="store_true", help="不生成 YAML 元数据头")
    parser.add_argument("--stdout", action="store_true", help="输出到标准输出")

    args = parser.parse_args()
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"错误: 文件不存在 — {args.input}", file=sys.stderr)
        sys.exit(1)

    result = convert(
        input_path,
        output_mode=args.mode,
        extract_images=not args.no_images,
        images_dir=args.images_dir,
        skip_cover=not args.no_skip_cover,
        frontmatter=not args.no_frontmatter,
    )

    if args.mode == "json":
        import json
        output_text = json.dumps(result["content"], ensure_ascii=False, indent=2)
    else:
        output_text = result["content"]

    if args.stdout:
        print(output_text)
    else:
        ext_map = {"html": ".html", "markdown": ".md", "json": ".json"}
        output_path = Path(args.output or input_path.with_suffix(ext_map[args.mode]))
        output_path.write_text(output_text, encoding="utf-8")
        print(f"转换完成: {input_path} → {output_path}")
        if result["images"]:
            print(f"提取图片: {len(result['images'])} 张")


if __name__ == "__main__":
    main()
