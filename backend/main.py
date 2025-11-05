from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
from pathlib import Path
from fastapi.responses import PlainTextResponse
import glob

DB_PATH = Path("queue.db")

app = FastAPI(title="QueueCTL Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def connect_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.get("/jobs")
def get_jobs():
    conn = connect_db()
    rows = conn.execute("SELECT * FROM jobs ORDER BY updated_at DESC").fetchall()
    return [dict(r) for r in rows]

@app.get("/dlq")
def get_dlq():
    conn = connect_db()
    rows = conn.execute("SELECT * FROM dlq ORDER BY failed_at DESC").fetchall()
    return [dict(r) for r in rows]

@app.get("/logs/{job_id}", response_class=PlainTextResponse)
def get_job_log(job_id: str):
    """Return the content of the latest log file for a given job."""
    log_dir = Path("logs")
    files = sorted(glob.glob(str(log_dir / f"{job_id}__*.log")), reverse=True)
    if not files:
        raise HTTPException(status_code=404, detail="No log found for this job")

    with open(files[0], "r", encoding="utf-8") as f:
        return f.read()

@app.get("/status")
def get_status():
    conn = connect_db()
    data = {}
    for r in conn.execute("SELECT state, COUNT(*) as count FROM jobs GROUP BY state"):
        data[r["state"]] = r["count"]
    workers = conn.execute("SELECT COUNT(*) FROM workers").fetchone()[0]
    return {"workers": workers, "jobs": data}

# 🔁 Retry DLQ job
@app.post("/dlq/retry/{job_id}")
def retry_dlq_job(job_id: str):
    conn = connect_db()
    with conn:
        r = conn.execute("SELECT * FROM dlq WHERE id=?", (job_id,)).fetchone()
        if not r:
            raise HTTPException(status_code=404, detail="Job not found in DLQ")
        conn.execute("""
            UPDATE jobs SET state='pending', attempts=0, next_run_at=datetime('now'), updated_at=datetime('now'),
            locked_by=NULL, locked_at=NULL WHERE id=?
        """, (job_id,))
        conn.execute("DELETE FROM dlq WHERE id=?", (job_id,))
    return {"message": f"Job {job_id} requeued successfully"}

# ❌ Delete completed job
@app.delete("/jobs/{job_id}")
def delete_job(job_id: str):
    conn = connect_db()
    with conn:
        result = conn.execute("DELETE FROM jobs WHERE id=?", (job_id,))
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Job not found")
    return {"message": f"Job {job_id} deleted successfully"}
