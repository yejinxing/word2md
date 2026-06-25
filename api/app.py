"""FastAPI 服务 — word2md REST API，可被 Dify 等第三方调用。"""

import tempfile
import shutil
from pathlib import Path
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse

from engine import DocxReader, SemanticParser, HtmlEmitter, MarkdownEmitter, JsonEmitter

app = FastAPI(
    title="word2md",
    description="Word (.docx) 报告高保真转换服务",
    version="0.1.0",
)

EMITTERS = {
    "html": HtmlEmitter(),
    "markdown": MarkdownEmitter(),
    "json": JsonEmitter(),
}


@app.get("/api/v1/health")
async def health():
    """健康检查。"""
    return {"status": "ok", "version": "0.1.0"}


@app.post("/api/v1/convert")
async def convert(
    file: UploadFile = File(...),
    output: str = Form("html"),
):
    """上传 .docx 文件，返回转换结果 JSON。"""
    if output not in EMITTERS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid output mode: {output}. Must be one of {list(EMITTERS.keys())}",
        )

    tmp_dir = tempfile.mkdtemp()
    try:
        file_path = Path(tmp_dir) / file.filename
        content = await file.read()
        file_path.write_bytes(content)

        reader = DocxReader(str(file_path))
        ir = SemanticParser(reader).parse()
        emitter = EMITTERS[output]
        body = emitter.emit(ir)

        stats = {
            "headings": sum(1 for n in ir.nodes if n.type == "heading"),
            "paragraphs": sum(1 for n in ir.nodes if n.type == "paragraph"),
            "tables": sum(1 for n in ir.nodes if n.type == "table"),
        }

        return {
            "success": True,
            "data": {
                "content": body,
                "metadata": {
                    "title": ir.title,
                    "author": ir.author,
                    "filename": file.filename,
                },
                "stats": stats,
            },
            "error": None,
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "data": None, "error": str(e)},
        )
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
