# ⚙️ QueueCTL — CLI-Based Background Job Queue System

QueueCTL is a **CLI-driven background job queue system** that supports worker-based execution, automatic retries with exponential backoff, and a **Dead Letter Queue (DLQ)** for failed jobs.  
It also includes a **FastAPI backend** and a **React + Tailwind web dashboard** for real-time monitoring and control.

---

## 🚀 Features

✅ Enqueue and manage background jobs via CLI  
✅ Multiple worker support for concurrent job execution  
✅ Automatic retries with exponential backoff  
✅ Dead Letter Queue (DLQ) for permanently failed jobs  
✅ Persistent storage using SQLite  
✅ REST API for job management  
✅ Web dashboard with live job status and logs  
✅ Configurable retry and backoff parameters  
✅ Graceful worker shutdowns  

---

## 🧱 Tech Stack

| Layer | Technology |
|-------|-------------|
| CLI & Core | Python 3 |
| Backend API | FastAPI |
| Database | SQLite |
| Frontend | React + Tailwind CSS (Vite) |
| Logging | Local file-based logging |
| Version Control | Git + GitHub |

---

## 🗂️ Folder Structure

```bash
QueueCTL_flam/
├── backend/                # FastAPI backend
│   └── main.py            # REST API (jobs, DLQ, logs)
├── frontend/              # React + Tailwind dashboard
│   ├── src/
│   │   ├── components/
│   │   │   └── JobTable.jsx
│   │   └── App.jsx
│   ├── package.json
│   └── vite.config.js
├── queuectl.py            # CLI-based job manager
├── queue.db               # SQLite persistent storage
├── logs/                  # Job execution logs
├── .gitignore
└── README.md
```

---

## ⚙️ Setup Instructions

### 🧩 1. Clone Repository

```bash
git clone https://github.com/error077-ux/QueueCTL_flam.git
cd QueueCTL_flam
```

### 🧩 2. Setup Python Environment

```bash
python -m venv venv
venv\Scripts\activate     # (Windows)
source venv/bin/activate  # (Linux/Mac)
pip install -r requirements.txt
```

### 🧩 3. Run CLI Commands

```bash
# Enqueue a job from JSON file
python queuectl.py enqueue "@job.json"

# Start 2 workers
python queuectl.py worker start --count 2

# Check system status
python queuectl.py status

# List all jobs
python queuectl.py list
```

### 🧩 4. Backend (FastAPI)

```bash
cd backend
uvicorn main:app --reload --port 8000
```

API will be available at: `http://localhost:8000`

### 🧩 5. Frontend (React + Tailwind Dashboard)

```bash
cd frontend
npm install
npm run dev
```

Dashboard will be available at: `http://localhost:5173`

**You'll See:**
- System status (active workers, job counts)
- Tables for "All Jobs" and "Dead Letter Queue"
- Buttons for Retry, Delete, and View Log

---

## 🧠 Architecture Overview

### Job States

| State        | Description                      |
|--------------|----------------------------------|
| `pending`    | Waiting for worker               |
| `processing` | Currently being executed         |
| `completed`  | Executed successfully            |
| `failed`     | Failed but retryable             |
| `dead`       | Permanently failed, moved to DLQ |

### Components Interaction

```
+--------------+        +--------------+        +--------------+
|   CLI Tool   | --->   |  SQLite DB   | <---   |   FastAPI    |
| (queuectl.py)|        |  (queue.db)  |        |   Backend    |
+--------------+        +--------------+        +--------------+
                                      |
                                      v
                            +----------------------+
                            |  React + Tailwind UI |
                            |  (Live Dashboard)    |
                            +----------------------+
```

---

## 🧪 Testing the System

| Scenario         | Expected Result                 |
|------------------|---------------------------------|
| Enqueue + Worker | Job executed successfully       |
| Failing Job      | Retries automatically (backoff) |
| Exceed retries   | Moves to DLQ                    |
| Retry DLQ        | Job requeued to pending         |
| Delete job       | Removed from DB and UI          |
| Log view         | Shows captured command output   |

---

## 📊 Example CLI Output

```bash
> python queuectl.py status
Workers: 2
pending     1
processing  0
completed   3
failed      0
dead        1
```

---

## 🧰 Configuration

```bash
# Set maximum retry attempts
python queuectl.py config set max-retries 3

# Set exponential backoff base
python queuectl.py config set backoff-base 2
```

---

## 📝 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/jobs` | List all jobs |
| GET | `/api/jobs/{job_id}` | Get job details |
| POST | `/api/jobs` | Create new job |
| DELETE | `/api/jobs/{job_id}` | Delete job |
| GET | `/api/dlq` | List DLQ jobs |
| POST | `/api/dlq/{job_id}/retry` | Retry DLQ job |
| GET | `/api/logs/{job_id}` | Get job logs |
| GET | `/api/status` | Get system status |

---

## 🤝 Contribution

Pull requests are welcome!  
For major changes, open an issue first to discuss what you'd like to change.

---

## 🧑‍💻 Author

**Aniruth S**  
💼 Backend Developer | Blockchain Enthusiast  
📧 your-email@example.com  
🔗 [GitHub Profile](https://github.com/error077-ux)

---

