"""CLI — word2md 命令行入口，支持单文件和批量转换。"""

import argparse
import glob
import sys
from pathlib import Path
from engine import convert


def convert_one(input_path: Path, args) -> tuple:
    """转换单个文件，返回 (ok: bool, message: str)。"""
    try:
        result = convert(
            input_path,
            output_mode=args.mode,
            extract_images=not args.no_images,
            images_dir=args.images_dir,
            skip_cover=args.skip_cover,
            frontmatter=args.frontmatter,
        )
        ext_map = {"html": ".html", "markdown": ".md", "json": ".json"}
        ext = ext_map[args.mode]

        # 输出路径
        if args.output_dir:
            output_path = Path(args.output_dir) / input_path.with_suffix(ext).name
        elif args.output:
            output_path = Path(args.output)
        else:
            output_path = input_path.with_suffix(ext)

        output_path.parent.mkdir(parents=True, exist_ok=True)

        if args.mode == "json":
            import json
            text = json.dumps(result["content"], ensure_ascii=False, indent=2)
        else:
            text = result["content"]

        output_path.write_text(text, encoding="utf-8")
        imgs = f", {len(result['images'])} 张图片" if result["images"] else ""
        return (True, f"{input_path.name} → {output_path}{imgs}")
    except Exception as e:
        return (False, f"{input_path.name}: {e}")


def main():
    parser = argparse.ArgumentParser(
        prog="word2md",
        description="Word (.docx) → HTML / Markdown / JSON（支持批量）",
    )
    parser.add_argument(
        "inputs", nargs="+", type=str,
        help="输入 .docx / .doc 文件（支持通配符，如 *.docx *.doc）",
    )
    parser.add_argument("-o", "--output", type=str, default=None,
                        help="输出文件路径（单文件模式）")
    parser.add_argument("-d", "--output-dir", type=str, default=None,
                        help="输出目录（批量模式）")
    parser.add_argument("--mode", type=str, default="html",
                        choices=["html", "markdown", "json"],
                        help="输出格式 (默认: html)")
    parser.add_argument("--no-images", action="store_true", help="不提取图片")
    parser.add_argument("--images-dir", type=str, default=None, help="图片输出目录")
    parser.add_argument("--skip-cover", action="store_true", help="跳过封面页")
    parser.add_argument("--frontmatter", action="store_true", help="生成 YAML 元数据头")
    parser.add_argument("--stdout", action="store_true", help="输出到标准输出（单文件）")

    args = parser.parse_args()

    # 展开通配符
    files = []
    for pattern in args.inputs:
        matched = glob.glob(pattern)
        if matched:
            files.extend(Path(f) for f in matched)
        else:
            p = Path(pattern)
            if p.is_dir():
                files.extend(p.glob("*.docx"))
                files.extend(p.glob("*.doc"))
            elif p.exists():
                files.append(p)
            else:
                print(f"警告: 未找到匹配文件 — {pattern}", file=sys.stderr)

    if not files:
        print("错误: 没有找到任何 .docx/.doc 文件", file=sys.stderr)
        sys.exit(1)

    # 去重
    files = sorted(set(f.resolve() for f in files))

    # stdout 仅单文件
    if args.stdout and len(files) > 1:
        print("错误: --stdout 仅支持单文件转换", file=sys.stderr)
        sys.exit(1)

    # 执行转换
    ok = 0
    for i, fp in enumerate(files, 1):
        tag = f"[{i}/{len(files)}]" if len(files) > 1 else ""
        success, msg = convert_one(fp, args)
        status = "OK" if success else "FAIL"
        print(f"{status} {tag} {msg}")
        if success:
            ok += 1

    if len(files) > 1:
        print(f"\n完成: {ok}/{len(files)} 个文件转换成功")


if __name__ == "__main__":
    main()
