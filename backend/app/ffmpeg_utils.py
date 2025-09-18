# backend/app/ffmpeg_utils.py
import subprocess
import json
import shlex
import os
from typing import Dict, List, Tuple

def run_cmd(cmd: list):
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return proc.returncode, proc.stdout, proc.stderr

def get_video_info(path: str) -> Dict:
    """Return dict: {duration: float_seconds, width: int, height: int}"""
    # duration
    cmd_dur = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        path
    ]
    proc = subprocess.run(cmd_dur, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    duration = float(proc.stdout.strip() or 0.0)

    # widthxheight
    cmd_wh = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=p=0:s=x",
        path
    ]
    proc2 = subprocess.run(cmd_wh, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    wh = proc2.stdout.strip()
    if 'x' in wh:
        width, height = map(int, wh.split('x'))
    else:
        width = height = None

    return {"duration": duration, "width": width, "height": height}


def build_ffmpeg_command(input_path: str, overlays: List[Dict], output_path: str, video_width: int, video_height: int) -> List[str]:
    """
    overlays: list of dicts like:
    {
      "type": "text"|"image"|"video",
      "content": "hello"               # for text
      "source": "/path/to/file.png"    # for image/video overlay
      "x_percent": 0.1, "y_percent": 0.2  # relative positions [0..1]
      "start_time": 2.5, "end_time": 5.0
      "scale": 0.2                      # optional scale factor for overlays
    }
    """
    # We'll convert percent -> pixels
    def px_x(p): return int(p * video_width)
    def px_y(p): return int(p * video_height)

    inputs = ["-y", "-i", input_path]
    extra_input_index = 1  # ffmpeg's additional inputs start at 1 (0 is main video)
    for ov in overlays:
        if ov["type"] in ("image", "video"):
            inputs += ["-i", ov["source"]]

    filters = []
    label_counter = 0
    current_label = "[0:v]"

    # apply text overlays first (they don't need extra inputs)
    for ov in overlays:
        if ov["type"] == "text":
            text = ov["content"].replace(":", "\\:").replace("'", "\\'")
            x = px_x(ov.get("x_percent", 0.5))
            y = px_y(ov.get("y_percent", 0.5))
            start = ov.get("start_time", 0)
            end = ov.get("end_time", start + 5)
            draw = (f"{current_label} drawtext="
                    f"text='{text}':x={x}:y={y}:fontsize=48:box=1:boxcolor=black@0.5:boxborderw=5:"
                    f"enable='between(t,{start},{end})' [v{label_counter}]")
            filters.append(draw)
            current_label = f"[v{label_counter}]"
            label_counter += 1

    # now overlay image/video overlays (these consume extra inputs)
    input_idx = 1
    for ov in overlays:
        if ov["type"] in ("image", "video"):
            x = px_x(ov.get("x_percent", 0.5))
            y = px_y(ov.get("y_percent", 0.5))
            start = ov.get("start_time", 0)
            end = ov.get("end_time", start + 5)
            # optional scaling for image/video overlay
            scale = ov.get("scale")
            overlay_input_label = f"[{input_idx}:v]"
            ov_filter_label = f"[v{label_counter}]"
            if scale:
                # scale overlay input first, e.g. [1:v] scale=iw*0.2:-1 [s1]; then overlay s1
                s_label = f"[s{label_counter}]"
                filters.append(f"{overlay_input_label} scale=iw*{scale}:-1 {s_label}")
                overlay_input_label = s_label
            # overlay filter
            filters.append(f"{current_label}{overlay_input_label} overlay=x={x}:y={y}:enable='between(t,{start},{end})' {ov_filter_label}")
            current_label = ov_filter_label
            label_counter += 1
            input_idx += 1

    # if no filters (no overlays), just copy input -> output
    cmd = ["ffmpeg"] + inputs
    if filters:
        filter_complex = "; ".join(filters)
        cmd += ["-filter_complex", filter_complex, "-map", current_label, "-map", "0:a?", "-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-c:a", "copy", output_path]
    else:
        cmd += ["-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-c:a", "copy", output_path]

    return cmd
