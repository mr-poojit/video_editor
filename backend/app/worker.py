import os
import json
import time
import subprocess
from datetime import datetime
from .db import get_session
from .models import Job
from .ffmpeg_utils import get_video_info, build_ffmpeg_command
from sqlmodel import select
from datetime import datetime

def parse_out_time(time_str: str) -> float:
    """Convert HH:MM:SS.micro to seconds."""
    try:
        h, m, s = time_str.split(":")
        return int(h) * 3600 + int(m) * 60 + float(s)
    except Exception:
        return 0.0


def process_job(job_id: str):
    session = get_session()
    job = session.get(Job, job_id)
    if not job:
        session.close()
        return

    try:
        job.status = "processing"
        job.progress = 0.0
        job.updated_at = datetime.now()
        session.add(job)
        session.commit()

        # Parse metadata
        if isinstance(job.overlay_metadata, str):
            overlays_data = json.loads(job.overlay_metadata)
        else:
            overlays_data = job.overlay_metadata or {}

        overlays = overlays_data.get("overlays", [])

        # Get video info
        info = get_video_info(job.input_path)
        duration = info.get("duration")
        width = info.get("width")
        height = info.get("height")

        # Prepare output
        out_dir = os.path.join(os.path.dirname(job.input_path), "out")
        os.makedirs(out_dir, exist_ok=True)
        output_path = os.path.join(out_dir, f"{job.id}_rendered.mp4")

        cmd = build_ffmpeg_command(
            job.input_path,
            overlays,
            output_path,
            width or 1280,
            height or 720
        )

        # Add progress tracking
        cmd_with_progress = cmd + ["-progress", "pipe:1", "-nostats"]

        proc = subprocess.Popen(
            cmd_with_progress,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )

        last_progress = 0.0
        while True:
            line = proc.stdout.readline()
            if not line:
                if proc.poll() is not None:
                    break
                time.sleep(0.1)
                continue

            line = line.strip()

            # Progress time
            if line.startswith("out_time="):
                out_time = parse_out_time(line.split("=", 1)[1])
                prog = (out_time / duration * 100.0) if duration else 0.0
                prog = round(min(100.0, prog), 2)

                # Commit only if progress increased >= 1%
                if prog - last_progress >= 1.0:
                    job.progress = prog
                    job.updated_at = datetime.now()
                    session.add(job)
                    session.commit()
                    last_progress = prog

            # End marker
            if line.startswith("progress=") and line.endswith("end"):
                job.progress = 100.0
                job.status = "done"
                job.output_path = output_path
                job.updated_at = datetime.now()
                session.add(job)
                session.commit()

        proc.wait()

        # Handle errors
        if proc.returncode != 0:
            stderr = proc.stderr.read()
            job.status = "failed"
            job.message = f"ffmpeg failed: {stderr[:200]}"
            session.add(job)
            session.commit()

    except Exception as e:
        job.status = "failed"
        job.message = str(e)
        job.updated_at = datetime.now()
        session.add(job)
        session.commit()

    finally:
        session.close()
