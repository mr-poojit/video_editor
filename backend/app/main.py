# backend/app/main.py
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, HTTPException, Request
from fastapi.responses import JSONResponse, FileResponse
from sqlmodel import SQLModel
from .db import init_db, get_session
from .models import Job
from uuid import uuid4
from datetime import datetime
import os, aiofiles, json
from .worker import process_job

app = FastAPI(title="Buttercut Video Renderer")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STORAGE_DIR = os.environ.get("STORAGE_DIR", os.path.join(BASE_DIR, "storage"))
os.makedirs(STORAGE_DIR, exist_ok=True)

@app.on_event("startup")
def startup():
    init_db()
    os.makedirs(STORAGE_DIR, exist_ok=True)

async def save_upload_file(upload_file: UploadFile, destination: str):
    async with aiofiles.open(destination, 'wb') as out_file:
        while True:
            chunk = await upload_file.read(1024*1024)
            if not chunk:
                break
            await out_file.write(chunk)
    await upload_file.close()

@app.post("/upload")
async def upload(
    background_tasks: BackgroundTasks,
    video: UploadFile = File(...),
    metadata: str = Form(...)
):
    job_id = str(uuid4())
    job_dir = os.path.join(STORAGE_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)

    input_path = os.path.join(job_dir, "input" + os.path.splitext(video.filename)[1])
    await save_upload_file(video, input_path)

    # parse metadata safely
    try:
        parsed = json.loads(metadata)
    except Exception:
        parsed = {"text": metadata}

    # save job
    session = get_session()
    job = Job(
        id=job_id,
        status="queued",
        progress=0.0,
        input_path=input_path,
        overlay_metadata=json.dumps(parsed)  # store as string
    )
    session.add(job)
    session.commit()
    session.close()

    background_tasks.add_task(process_job, job_id)

    return {
        "job_id": job_id,
        "status_url": f"/status/{job_id}",
        "result_url": f"/result/{job_id}"
    }

@app.get("/status/{job_id}")
def get_status(job_id: str):
    session = get_session()
    job = session.get(Job, job_id)
    session.close()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # decode overlay_metadata safely
    metadata = None
    if job.overlay_metadata:
        try:
            metadata = json.loads(job.overlay_metadata)
        except Exception:
            metadata = {"raw": str(job.overlay_metadata)}

    return {
        "job_id": job.id,
        "status": job.status,
        "progress": job.progress,
        "message": job.message,
        "metadata": metadata
    }

@app.get("/result/{job_id}")
def result(job_id: str):
    session = get_session()
    job = session.get(Job, job_id)
    session.close()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "done" or not job.output_path or not os.path.exists(job.output_path):
        raise HTTPException(status_code=404, detail="Result not ready")
    return FileResponse(path=job.output_path, filename=os.path.basename(job.output_path), media_type="video/mp4")
