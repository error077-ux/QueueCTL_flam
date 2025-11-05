#!/usr/bin/env python3
import argparse, datetime as dt, json, os, signal, sqlite3, subprocess, sys, time
from pathlib import Path
from typing import Optional

DB_PATH = Path("queue.db")
DATEFMT = "%Y-%m-%dT%H:%M:%SZ"

SCHEMA_SQL = r"""
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY,
  command TEXT NOT NULL,
  state TEXT NOT NULL DEFAULT 'pending',
  attempts INTEGER NOT NULL DEFAULT 0,
  max_retries INTEGER NOT NULL DEFAULT 3,
  timeout_seconds INTEGER DEFAULT 0,
  priority INTEGER DEFAULT 0,
  run_at TEXT DEFAULT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  next_run_at TEXT NOT NULL,
  locked_by TEXT,
  locked_at TEXT
);
CREATE TABLE IF NOT EXISTS dlq (
  id TEXT PRIMARY KEY,
  command TEXT NOT NULL,
  attempts INTEGER NOT NULL,
  max_retries INTEGER NOT NULL,
  failed_at TEXT NOT NULL,
  last_error TEXT
);
CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS workers (pid INTEGER PRIMARY KEY,started_at TEXT NOT NULL);
"""

DEFAULT_CONFIG = {
    "backoff_base": "2",
    "default_max_retries": "3",
    "poll_interval_seconds": "1",
    "shutdown_flag": "0",
    "job_timeout_seconds": "0",
    "log_dir": "logs",
}

def connect_db():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    conn = connect_db()
    with conn:
        conn.executescript(SCHEMA_SQL)
        for k,v in DEFAULT_CONFIG.items():
            conn.execute("INSERT OR IGNORE INTO config VALUES (?,?)",(k,v))
    conn.close()

def utcnow(): 
    return dt.datetime.now(dt.UTC)
def now_iso(): 
    return utcnow().strftime(DATEFMT)

def cfg_get(conn,key):
    cur=conn.execute("SELECT value FROM config WHERE key=?",(key,)); r=cur.fetchone()
    return r[0] if r else DEFAULT_CONFIG.get(key,"")

def cfg_set(conn,key,val):
    with conn: conn.execute("INSERT INTO config VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(key,val))

# ---------- enqueue ----------
def cmd_enqueue(a):
    init_db()
    if a.job_json.startswith("@"):
        with open(a.job_json[1:],encoding="utf-8") as f: p=json.load(f)
    else: p=json.loads(a.job_json)

    run_at = p.get("run_at", now_iso())
    next_run = run_at
    timeout = int(p.get("timeout_seconds", 0))
    priority = int(p.get("priority", 0))

    conn = connect_db()
    with conn:
        conn.execute("""
        INSERT INTO jobs(id,command,state,attempts,max_retries,timeout_seconds,priority,run_at,
                         created_at,updated_at,next_run_at,locked_by,locked_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(id) DO UPDATE SET
          command=excluded.command,
          state='pending',
          attempts=0,
          updated_at=excluded.updated_at,
          next_run_at=excluded.next_run_at,
          timeout_seconds=excluded.timeout_seconds,
          priority=excluded.priority,
          run_at=excluded.run_at,
          locked_by=NULL,
          locked_at=NULL
        """,
        (p["id"],p["command"],p.get("state","pending"),p.get("attempts",0),
         p.get("max_retries",int(cfg_get(conn,"default_max_retries"))),
         timeout,priority,run_at,
         now_iso(),now_iso(),next_run,None,None))
    print(f"Enqueued job {p['id']} (priority={priority}, run_at={run_at})")

# ---------- list/status ----------
def cmd_status(a):
    init_db(); c=connect_db()
    cur=c.execute("SELECT state,COUNT(*) c FROM jobs GROUP BY state")
    d={r[0]:r[1] for r in cur.fetchall()}
    w=c.execute("SELECT COUNT(*) FROM workers").fetchone()[0]
    print("Workers:",w)
    for s in ["pending","processing","completed","failed","dead"]:
        print(f"{s:10s}",d.get(s,0))

def cmd_list(a):
    init_db(); c=connect_db()
    q="SELECT * FROM jobs" if not a.state else "SELECT * FROM jobs WHERE state=? ORDER BY priority DESC"
    cur=c.execute(q,(a.state,) if a.state else ())
    for r in cur.fetchall(): print(json.dumps(dict(r)))

# ---------- worker ----------
def claim_job(conn)->Optional[sqlite3.Row]:
    now=now_iso()
    cur=conn.execute("""
        SELECT id FROM jobs
        WHERE state='pending' AND next_run_at<=? AND (run_at IS NULL OR run_at<=?)
        ORDER BY priority DESC, created_at ASC LIMIT 1
    """,(now,now))
    r=cur.fetchone()
    if not r: return None
    jid=r["id"]
    with conn:
        u=conn.execute("UPDATE jobs SET state='processing',locked_by=?,locked_at=?,updated_at=? WHERE id=? AND state='pending'",
                       (os.getpid(),now,now,jid))
    if u.rowcount==0: return None
    return conn.execute("SELECT * FROM jobs WHERE id=?",(jid,)).fetchone()

def run_job(conn,job):
    timeout = job["timeout_seconds"] or int(cfg_get(conn,"job_timeout_seconds"))
    logdir=Path(cfg_get(conn,"log_dir")); logdir.mkdir(exist_ok=True)
    logf=logdir/f"{job['id']}__{int(time.time())}.log"
    try:
        res=subprocess.run(job["command"],shell=True,capture_output=True,text=True,
                           timeout=timeout if timeout>0 else None)
        ok=res.returncode==0
        with open(logf,"w",encoding="utf-8") as f:
            f.write(f"$ {job['command']}\\n\\n{res.stdout}\\n{res.stderr}\\nExit:{res.returncode}\\n")
    except subprocess.TimeoutExpired:
        ok=False
        with open(logf,"w",encoding="utf-8") as f: f.write(f"[timeout] exceeded {timeout}s\\n")

    with conn:
        if ok:
            conn.execute("UPDATE jobs SET state='completed',updated_at=?,locked_by=NULL,locked_at=NULL WHERE id=?",
                         (now_iso(),job["id"]))
        else:
            attempts=job["attempts"]+1
            base=int(cfg_get(conn,"backoff_base"))
            delay=base**attempts
            if attempts>job["max_retries"]:
                conn.execute("UPDATE jobs SET state='dead',attempts=?,updated_at=? WHERE id=?",(attempts,now_iso(),job["id"]))
                conn.execute("INSERT OR REPLACE INTO dlq VALUES (?,?,?,?,?,?)",
                             (job["id"],job["command"],attempts,job["max_retries"],now_iso(),"failed"))
            else:
                nxt=(utcnow()+dt.timedelta(seconds=delay)).strftime(DATEFMT)
                conn.execute("""UPDATE jobs SET state='pending',attempts=?,next_run_at=?,updated_at=?,locked_by=NULL,locked_at=NULL
                                WHERE id=?""",(attempts,nxt,now_iso(),job["id"]))

def worker_loop():
    init_db(); conn=connect_db(); pid=os.getpid()
    with conn: conn.execute("INSERT OR REPLACE INTO workers VALUES (?,?)",(pid,now_iso()))
    try:
        while True:
            if cfg_get(conn,"shutdown_flag")=="1": break
            job=claim_job(conn)
            if job: run_job(conn,job)
            else: time.sleep(int(cfg_get(conn,"poll_interval_seconds")))
    finally:
        with conn: conn.execute("DELETE FROM workers WHERE pid=?",(pid,)); conn.close()

def cmd_worker_start(a):
    init_db()
    conn = connect_db()
    cfg_set(conn, "shutdown_flag", "0")

    import threading
    for _ in range(max(1, a.count)):
        t = threading.Thread(target=worker_loop, daemon=True)
        t.start()

    print(f"Started {a.count} worker(s). Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping workers...")
        cfg_set(conn, "shutdown_flag", "1")

# ---------- DLQ ----------
def cmd_dlq_list(a):
    init_db(); c=connect_db()
    for r in c.execute("SELECT * FROM dlq ORDER BY failed_at DESC"): print(json.dumps(dict(r)))

def cmd_dlq_retry(a):
    init_db(); c=connect_db()
    with c:
        r=c.execute("SELECT * FROM dlq WHERE id=?",(a.job_id,)).fetchone()
        if not r: print("No such job in DLQ"); return
        c.execute("""UPDATE jobs SET state='pending',attempts=0,next_run_at=?,updated_at=?,locked_by=NULL,locked_at=NULL WHERE id=?""",
                  (now_iso(),now_iso(),a.job_id))
        c.execute("DELETE FROM dlq WHERE id=?",(a.job_id,))
    print(f"Requeued DLQ job {a.job_id}")

# ---------- parser ----------
def build_parser():
    p=argparse.ArgumentParser(prog="queuectl",description="QueueCTL with timeouts, scheduling & priority")
    sub=p.add_subparsers(dest="cmd",required=True)
    p_enq=sub.add_parser("enqueue"); p_enq.add_argument("job_json"); p_enq.set_defaults(func=cmd_enqueue)
    p_st=sub.add_parser("status"); p_st.set_defaults(func=cmd_status)
    p_ls=sub.add_parser("list"); p_ls.add_argument("--state"); p_ls.set_defaults(func=cmd_list)
    p_w=sub.add_parser("worker"); sw=p_w.add_subparsers(dest="wcmd",required=True)
    ws=sw.add_parser("start"); ws.add_argument("--count",type=int,default=1); ws.set_defaults(func=cmd_worker_start)
    p_dlq=sub.add_parser("dlq"); sd=p_dlq.add_subparsers(dest="dcmd",required=True)
    sd.add_parser("list").set_defaults(func=cmd_dlq_list)
    r=sd.add_parser("retry"); r.add_argument("job_id"); r.set_defaults(func=cmd_dlq_retry)
    return p

def main(argv=None):
    init_db(); a=build_parser().parse_args(argv); a.func(a)

if __name__=="__main__": main()
