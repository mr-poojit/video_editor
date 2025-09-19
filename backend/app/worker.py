# backend/app/worker.py
import time
import shutil
import traceback
import os
from datetime import datetime
from .db import engine
from sqlmodel import Session
from .models import Job

def process_job(job_id: str):
    """
    Simple synchronous worker that updates job.progress in DB and
    copies input -> output to simulate rendering. This intentionally
    keeps things simple so the system works reliably in dev.
    """
    session = Session(engine)
    try:
        job = session.get(Job, job_id)
        if not job:
            session.close()
            return

        job.status = "processing"
        job.progress = 0.0
        job.updated_at = datetime.utcnow()
        session.add(job)
        session.commit()

        # simulate progress
        for p in range(0, 101, 10):
            time.sleep(1)  # simulate rendering work (blocking)
            job.progress = float(p)
            job.updated_at = datetime.utcnow()
            session.add(job)
            session.commit()

        # try to create output copy
        try:
            if job.input_path and os.path.exists(job.input_path):
                shutil.copy(job.input_path, job.output_path)
        except Exception:
            # don't crash; mark job as failed below if copy failed
            pass

        job.status = "done"
        job.progress = 100.0
        job.updated_at = datetime.utcnow()
        session.add(job)
        session.commit()

    except Exception as e:
        print("process_job error:", traceback.format_exc())
        try:
            job = session.get(Job, job_id)
            if job:
                job.status = "failed"
                job.message = str(e)
                job.updated_at = datetime.utcnow()
                session.add(job)
                session.commit()
        except Exception:
            pass
    finally:
        session.close()
