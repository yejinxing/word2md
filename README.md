# word2md

[![Python](https://img.shields.io/badge/Python-3.9+-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.138-teal?logo=fastapi)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-green)](./LICENSE)
[![Tests](https://img.shields.io/badge/Tests-17_passed-brightgreen)]()
[![LibreOffice](https://img.shields.io/badge/.doc-LibreOffice-orange?logo=libreoffice)](https://libreoffice.org)

> Word (.docx / .doc) → HTML / Markdown / JSON 高保真转换工具  
> 面向 **LLM 消费**优化，支持 CLI / Python API / FastAPI 服务 / Docker 部署
>
> ⚠️ **.docx 原生支持（高保真）**，.doc 通过 LibreOffice 转换为 .docx 后再处理，可能有损耗。建议优先使用 .docx。

---

## 为什么用 word2md？

大多数 DOCX 转 Markdown 工具（Pandoc、Mammoth、MarkItDown）能处理简单文档，但在表格合并单元格、自动编号、Wingdings 勾选框、域代码、脚注等细节上存在缺陷。word2md 从零构建，直接解析 OOXML，重点解决这些「最后一公里」问题：

- ✅ 垂直合并单元格 (vMerge) + 水平合并 (gridSpan)
- ✅ 自动编号（中文一/二/三、decimal、Roman、字母、多级 1.1）
- ✅ 表格列宽对齐（tblGrid + colgroup）
- ✅ Wingdings 勾选框 ☐/☑
- ✅ 域代码处理（fldChar begin/separate/end）
- ✅ 目录(TOC)智能检测与跳过
- ✅ 下划线空白占位符 `<u>&nbsp;...&nbsp;</u>`
- ✅ YAML frontmatter 元数据提取

---

## 快速开始

### 安装

```bash
# 创建虚拟环境
conda create -n word2md python=3.11 -y && conda activate word2md

# 安装
pip install -e .
```

### 命令行

```bash
word2md report.docx                          # 默认输出 HTML
word2md report.docx -o output.md --mode markdown
word2md report.docx --mode json --stdout     # JSON 输出到标准输出
word2md report.docx --no-images              # 不提取图片
word2md report.docx --skip-cover             # 跳过封面页
word2md report.docx --images-dir ./pics      # 指定图片目录
```

### Python

```python
from engine import convert

result = convert("report.docx", output_mode="html")
print(result["content"])       # HTML 字符串
print(result["metadata"])      # {"title": "...", "author": "...", "date": "..."}
print(result["stats"])         # {"headings": 130, "paragraphs": 634, "tables": 22}
print(result["images"])        # [{"id": "rId9", "filename": "image_rId9.jpeg", ...}]
```

---

## API 服务

### 启动

```bash
uvicorn api.app:app --host 0.0.0.0 --port 8088
```

浏览器打开 `http://localhost:8088/docs` 查看 Swagger 交互文档。

### 端点

| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| `GET` | `/api/v1/health` | — | `{"status":"ok","version":"0.1.0"}` |
| `POST` | `/api/v1/convert/html` | `file`, `extract_images`, `skip_cover` | 返回 HTML |
| `POST` | `/api/v1/convert/markdown` | 同上 | 返回 Markdown |
| `POST` | `/api/v1/convert/json` | 同上 | 返回 JSON IR |

### 参数说明

| 参数 | 类型 | 默认 | 说明 |
|------|------|:---:|------|
| `file` | UploadFile | 必填 | .docx 文件 |
| `extract_images` | bool | `true` | 是否提取嵌入图片 |
| `skip_cover` | bool | `false` | 是否跳过封面页 |

### 响应格式

```json
{
  "success": true,
  "data": {
    "content": "<h1>第一章  投标邀请</h1><p>...",
    "metadata": {
      "title": "招标文件",
      "author": "admin",
      "date": "2024-01-02",
      "filename": "report.docx"
    },
    "stats": {
      "headings": 130,
      "paragraphs": 634,
      "tables": 22,
      "images": 1
    },
    "images": [
      {
        "id": "rId9",
        "filename": "image_rId9.jpeg",
        "path": "tests/output/images/image_rId9.jpeg",
        "size": 50612
      }
    ]
  },
  "error": null
}
```

### cURL 示例

```bash
# HTML
curl -X POST http://localhost:8088/api/v1/convert/html \
  -F "file=@report.docx"

# Markdown
curl -X POST http://localhost:8088/api/v1/convert/markdown \
  -F "file=@report.docx" -F "extract_images=false"

# JSON
curl -X POST http://localhost:8088/api/v1/convert/json \
  -F "file=@report.docx" -F "skip_cover=true"
```

---

## Docker 部署

```bash
docker-compose up -d    # 启动在 8088 端口（镜像约 2.2GB，含 LibreOffice 支持 .doc）
```

> Docker 镜像基于 `python:3.11` + LibreOffice，同时支持 `.docx` 和 `.doc`。
> 仅需 `.docx` 可改用 `python:3.11-slim` 基础镜像（约 200MB）。

---

## Dify 集成

Dify 工作流由两步组成：**HTTP 请求节点** → **代码节点**提取内容。

### 步骤 1：HTTP 请求节点

| 配置项 | 值 |
|--------|-----|
| 方法 | `POST` |
| URL | `http://192.168.32.200:8088/api/v1/convert/html` |
| Body 类型 | `form-data` |
| 参数 | `file` = `{{file}}` |

三种端点可选：

| 端点 | 适用场景 |
|------|---------|
| `/convert/html` | 浏览器渲染、Dify 直接展示 |
| `/convert/markdown` | LLM 节点消费（token 友好） |
| `/convert/json` | 程序二次处理 |

### 步骤 2：代码节点（提取 content）

```python
import json

def main(http_response: str) -> dict:
    """从 HTTP 节点返回的 JSON 中提取 content 字段。"""
    try:
        data = json.loads(http_response)
        content = data.get("data", {}).get("content")
        return {"result": content}
    except (json.JSONDecodeError, AttributeError):
        return {"result": None}
```

### 步骤 3：LLM 节点

将代码节点的 `result` 作为输入传入 LLM 节点：

```
请分析以下招标文件内容：
{{code_node.result}}
```

---

## 格式覆盖

| Word 元素 | HTML 输出 | Markdown 输出 |
|-----------|----------|---------------|
| 标题 1-6 | `<h1>` ~ `<h6>` | `#` ~ `######` |
| 粗体 | `<strong>` | `**` |
| 斜体 | `<em>` | `*` |
| 下划线 | `<u>` | `<u>` (内嵌 HTML) |
| 删除线 | `<del>` | `~~` |
| 高亮 | `<mark>` | `<mark>` (内嵌 HTML) |
| 字体颜色 | `<span style="color:...">` | `<span>` (内嵌 HTML) |
| 勾选框 | ☐ / ☑ | ☐ / ☑ |
| 上标/下标 | `<sup>` / `<sub>` | `<sup>` / `<sub>` |
| 表格 | `<table>` + colspan/rowspan | GFM 或 HTML 表格 |
| 图片 | `<img src="...">` | `![alt](path)` |
| 编号 | 中文/数字/罗马/字母前缀 | 同 HTML（纯文本前缀） |
| 下划线占位 | `<u>&nbsp;...&nbsp;</u>` | `<u>&nbsp;...&nbsp;</u>` |

---

## 架构

```
.docx 文件
    │
    ▼
┌──────────────────────────────────────┐
│  Reader  (reader.py)                 │  ← ZIP + XML 解析
│  document.xml / styles.xml / rels    │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│  Parser  (parser.py)                 │  ← 段落/表格/图片/脚注识别
│  + NumberingResolver (numbering.py)  │  ← 自动编号中文/数字/罗马
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│  DocumentIR  (ir.py)                 │  ← 中间表示 AST
│  Span / IRNode / TableCell           │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│  Emitter  (emitter.py)               │
│  HtmlEmitter / Markdown / Json       │  ← 三种输出格式
└──────────────────────────────────────┘
```

---

## 项目结构

```
├── engine/
│   ├── reader.py         DOCX 读取（ZIP + XML）
│   ├── parser.py         语义解析（段落/表格/图片）
│   ├── ir.py             中间表示（Span / IRNode / TableCell）
│   ├── emitter.py        输出（HtmlEmitter / MarkdownEmitter / JsonEmitter）
│   └── numbering.py      自动编号解析（decimal / chineseCounting / Roman）
├── api/
│   └── app.py            FastAPI 服务（/convert/html /markdown /json）
├── cli.py                命令行入口
├── tests/
│   ├── test_engine.py    单元测试（17 tests）
│   └── fixtures/         测试用 .docx
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── requirements.txt
```

---

## 依赖

| 包 | 用途 |
|---|------|
| `python-docx` | DOCX 基础解析 |
| `fastapi` | Web 框架 |
| `uvicorn` | ASGI 服务器 |
| `python-multipart` | 文件上传 |
| `pyyaml` | YAML frontmatter |

---

## License

MIT
