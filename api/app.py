"""FastAPI — word2md 多端点 API（HTML / Markdown / JSON）。"""

import tempfile, shutil
from pathlib import Path
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from engine import convert

app = FastAPI(title="word2md", version="0.1.0",
              description="Word (.docx) 转 HTML/Markdown/JSON — 多端点独立调用")


async def _do_convert(file: UploadFile, mode: str, extract_images: bool, skip_cover: bool):
    tmp = tempfile.mkdtemp()
    try:
        fp = Path(tmp) / file.filename
        fp.write_bytes(await file.read())
        img_dir = Path(tmp) / "images" if extract_images else None
        return convert(str(fp), output_mode=mode, extract_images=extract_images,
                       images_dir=img_dir, skip_cover=skip_cover)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _ok(content, meta, stats, images, filename):
    return {"success": True,
            "data": {"content": content, "metadata": {**meta, "filename": filename},
                     "stats": stats, "images": images},
            "error": None}


@app.get("/api/v1/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


@app.post("/api/v1/convert/html")
async def convert_html(file: UploadFile = File(...), extract_images: bool = Form(True),
                        skip_cover: bool = Form(False)):
    r = await _do_convert(file, "html", extract_images, skip_cover)
    return _ok(r["content"], r["metadata"], r["stats"], r["images"], file.filename)


@app.post("/api/v1/convert/markdown")
async def convert_md(file: UploadFile = File(...), extract_images: bool = Form(True),
                      skip_cover: bool = Form(False)):
    r = await _do_convert(file, "markdown", extract_images, skip_cover)
    return _ok(r["content"], r["metadata"], r["stats"], r["images"], file.filename)


@app.post("/api/v1/convert/json")
async def convert_json(file: UploadFile = File(...), extract_images: bool = Form(True),
                        skip_cover: bool = Form(False)):
    r = await _do_convert(file, "json", extract_images, skip_cover)
    return _ok(r["content"], r["metadata"], r["stats"], r["images"], file.filename)
