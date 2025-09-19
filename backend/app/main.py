# backend/app/main.py
from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, WebSocket, Form, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session
from .db import init_db, get_session, engine
from .models import Job
from .worker import process_job
from uuid import uuid4
from datetime import datetime
import os, aiofiles, json, traceback, asyncio

app = FastAPI(title="Buttercut Video Renderer (dev)")

# --- STORAGE ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STORAGE_DIR = os.environ.get("STORAGE_DIR", os.path.join(BASE_DIR, "storage"))
os.makedirs(STORAGE_DIR, exist_ok=True)

# --- CORS for development ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # open for dev; lock down in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup():
    init_db()
    os.makedirs(STORAGE_DIR, exist_ok=True)

# Save uploaded file in chunks (async)
async def save_upload_file(upload_file: UploadFile, destination: str):
    async with aiofiles.open(destination, "wb") as out_file:
        while True:
            chunk = await upload_file.read(1024 * 1024)
            if not chunk:
                break
            await out_file.write(chunk)
    await upload_file.close()

@app.post("/upload")
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    overlays: str = Form(default="[]"),
    db: Session = Depends(get_session),
):
    """
    Accept:
      - multipart field 'file' -> UploadFile
      - form field 'overlays' -> stringified JSON (optional)
    Returns:
      - job_id
    """
    try:
        # parse overlays if possible to ensure valid JSON stored
        try:
            ov_data = json.loads(overlays) if overlays else []
        except Exception:
            ov_data = []

        job_id = str(uuid4())
        safe_filename = f"{job_id}_{(file.filename or 'upload')}"
        input_path = os.path.join(STORAGE_DIR, safe_filename)
        output_path = os.path.join(STORAGE_DIR, f"{job_id}_output.mp4")

        # save uploaded file
        await save_upload_file(file, input_path)

        # create DB Job entry (input_path must not be None)
        job = Job(
            id=job_id,
            status="queued",
            progress=0.0,
            input_path=input_path,
            output_path=output_path,
            overlay_metadata=json.dumps(ov_data),
            message="Uploaded. queued for processing",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        db.add(job)
        db.commit()
        db.refresh(job)

        # schedule background processing (synchronous worker runs off main request)
        background_tasks.add_task(process_job, job_id)

        return {"job_id": job_id}

    except Exception as e:
        print("upload_video exception:", traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@app.websocket("/render-progress")
async def render_progress(websocket: WebSocket):
    await websocket.accept()
    job_id = websocket.query_params.get("jobId") or websocket.query_params.get("job_id")
    if not job_id:
        await websocket.send_json({"error": "missing jobId query param"})
        await websocket.close(code=1008)
        return

    try:
        while True:
            # create a short session to read job
            session = Session(engine)
            job = session.get(Job, job_id)
            session.close()

            if not job:
                await websocket.send_json({"error": "job_not_found"})
                await websocket.close()
                return

            await websocket.send_json({"progress": job.progress, "status": job.status})

            if job.status in ("done", "failed"):
                output_url = None
                if job.status == "done":
                    # NOTE: if testing on device change 127.0.0.1 to your host IP
                    output_url = f"http://127.0.0.1:8000/result/{job_id}"
                await websocket.send_json({"status": job.status, "outputUrl": output_url})
                await websocket.close()
                return

            await asyncio.sleep(1.0)

    except Exception:
        print("render_progress websocket exception:", traceback.format_exc())
        try:
            await websocket.close()
        except Exception:
            pass


@app.get("/status/{job_id}")
def get_status(job_id: str, db: Session = Depends(get_session)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    try:
        metadata = json.loads(job.overlay_metadata) if job.overlay_metadata else None
    except Exception:
        metadata = {"raw": str(job.overlay_metadata)}

    return {
        "job_id": job.id,
        "status": job.status,
        "progress": job.progress,
        "message": job.message,
        "metadata": metadata,
    }


@app.get("/result/{job_id}")
def result(job_id: str, db: Session = Depends(get_session)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if not os.path.exists(job.output_path):
        raise HTTPException(status_code=404, detail="Result not ready")

    return FileResponse(
        path=job.output_path,
        filename=os.path.basename(job.output_path),
        media_type="video/mp4",
    )
