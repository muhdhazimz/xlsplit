from __future__ import annotations

import os
import sys
import io
import math
import threading
import webbrowser
import zipfile
from pathlib import Path
from typing import Any

import pandas as pd
from litestar import Litestar, get, post
from litestar.response import Response, Template
from litestar.datastructures import UploadFile
from litestar.enums import RequestEncodingType
from litestar.params import Body
from litestar.static_files import create_static_files_router
from litestar.contrib.jinja import JinjaTemplateEngine
from litestar.template.config import TemplateConfig

# ── PyInstaller path fix ──────────────────────────────────────────────────────
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).parent

# ── In-memory store ───────────────────────────────────────────────────────────
store: dict[str, Any] = {}

PORT = 8008


# ── Routes ───────────────────────────────────────────────────────────────────

@get("/")
async def index() -> Template:
    return Template(template_name="index.html")


@post("/upload")
async def upload(
    data: UploadFile = Body(media_type=RequestEncodingType.MULTI_PART),
) -> dict:
    filename = data.filename or ""
    ext = Path(filename).suffix.lower()

    if ext not in (".xlsx", ".xls", ".csv"):
        return {"error": "Only .xlsx, .xls, or .csv files are supported"}

    content = await data.read()
    buf = io.BytesIO(content)

    try:
        if ext == ".csv":
            df = pd.read_csv(buf)
        else:
            df = pd.read_excel(buf)
    except Exception as e:
        return {"error": f"Could not read file: {e}"}

    store["main"] = {
        "df": df,
        "filename": Path(filename).stem,
        "chunks": [],
    }

    columns = list(df.columns)
    preview = df.head(5).fillna("").astype(str).values.tolist()

    return {
        "total_rows": len(df),
        "columns": columns,
        "preview": preview,
        "filename": filename,
    }


@post("/split")
async def split(data: dict[str, Any]) -> dict:
    if "main" not in store:
        return {"error": "No file loaded"}

    rows_per_file = int(data.get("rows_per_file", 100))
    if rows_per_file < 100:
        return {"error": "Minimum is 100 rows per file"}

    df: pd.DataFrame = store["main"]["df"]
    total = len(df)
    num_files = math.ceil(total / rows_per_file)

    chunks = [df.iloc[i * rows_per_file:(i + 1) * rows_per_file] for i in range(num_files)]
    store["main"]["chunks"] = chunks

    files_info = []
    for i, chunk in enumerate(chunks):
        start = i * rows_per_file + 1
        end = min((i + 1) * rows_per_file, total)
        files_info.append({
            "index": i,
            "name": f"{store['main']['filename']}_part{i + 1}",
            "rows": len(chunk),
            "range": f"Rows {start}–{end}",
        })

    return {"num_files": num_files, "files": files_info}


@get("/download/{file_index:int}")
async def download_single(file_index: int, format: str = "csv") -> Response:
    if "main" not in store or not store["main"]["chunks"]:
        return Response(content=b"No split data", status_code=400)

    chunks: list[pd.DataFrame] = store["main"]["chunks"]
    base_name: str = store["main"]["filename"]
    fmt = format.lower()

    if file_index < 0 or file_index >= len(chunks):
        return Response(content=b"Invalid index", status_code=400)

    chunk = chunks[file_index]
    out_name = f"{base_name}_part{file_index + 1}"
    buf = io.BytesIO()

    if fmt == "xlsx":
        chunk.to_excel(buf, index=False)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        dl_name = f"{out_name}.xlsx"
    else:
        chunk.to_csv(buf, index=False)
        media_type = "text/csv"
        dl_name = f"{out_name}.csv"

    buf.seek(0)
    return Response(
        content=buf.read(),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{dl_name}"'},
    )


@get("/download-all")
async def download_all(format: str = "csv") -> Response:
    if "main" not in store or not store["main"]["chunks"]:
        return Response(content=b"No split data", status_code=400)

    chunks: list[pd.DataFrame] = store["main"]["chunks"]
    base_name: str = store["main"]["filename"]
    fmt = format.lower()

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, chunk in enumerate(chunks):
            out_name = f"{base_name}_part{i + 1}"
            file_buf = io.BytesIO()
            if fmt == "xlsx":
                chunk.to_excel(file_buf, index=False)
                fname = f"{out_name}.xlsx"
            else:
                chunk.to_csv(file_buf, index=False)
                fname = f"{out_name}.csv"
            file_buf.seek(0)
            zf.writestr(fname, file_buf.read())

    zip_buf.seek(0)
    return Response(
        content=zip_buf.read(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{base_name}_split.zip"'},
    )


# ── App ───────────────────────────────────────────────────────────────────────

def is_port_in_use(port: int) -> bool:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def open_browser() -> None:
    import time
    time.sleep(2.5)
    webbrowser.open(f"http://127.0.0.1:{PORT}")


@get("/shutdown")
async def shutdown() -> Response:
    threading.Thread(target=_shutdown).start()
    return Response(content=b"Shutting down...", status_code=200)

def _shutdown() -> None:
    import time
    time.sleep(0.5)
    os.kill(os.getpid(), 9)


app = Litestar(
    route_handlers=[
        index,
        upload,
        split,
        download_single,
        download_all,
        shutdown,
        create_static_files_router(path="/static", directories=[str(BASE_DIR / "static")]),
    ],
    template_config=TemplateConfig(
        directory=BASE_DIR / "templates",
        engine=JinjaTemplateEngine,
    ),
)


if __name__ == "__main__":
    import uvicorn

    if is_port_in_use(PORT):
        webbrowser.open(f"http://127.0.0.1:{PORT}")
        sys.exit(0)

    if sys.stdout is None:
        sys.stdout = open(os.devnull, 'w')
    if sys.stderr is None:
        sys.stderr = open(os.devnull, 'w')

    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=PORT,
        reload=False,
        log_config=None,
    )