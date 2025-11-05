import React, { useEffect, useState } from "react";
import axios from "axios";
import JobTable from "./components/JobTable";

export default function App() {
  const [status, setStatus] = useState({});
  const [jobs, setJobs] = useState([]);
  const [dlq, setDlq] = useState([]);

  const fetchData = async () => {
    try {
      const [statusRes, jobsRes, dlqRes] = await Promise.all([
        axios.get("http://127.0.0.1:8000/status"),
        axios.get("http://127.0.0.1:8000/jobs"),
        axios.get("http://127.0.0.1:8000/dlq"),
      ]);
      setStatus(statusRes.data);
      setJobs(jobsRes.data);
      setDlq(dlqRes.data);
    } catch (err) {
      console.error("Backend not reachable", err);
    }
  };

  useEffect(() => {
    fetchData();
    const timer = setInterval(fetchData, 3000); // auto-refresh every 3s
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <h1 className="text-3xl font-bold mb-4 text-blue-600">
        QueueCTL Dashboard
      </h1>

      <div className="mb-6 bg-white shadow p-4 rounded-lg">
        <h2 className="text-xl font-semibold mb-2">System Status</h2>
        <p className="mb-1">
          <strong>Active Workers:</strong> {status.workers ?? 0}
        </p>
        <pre className="bg-gray-100 p-2 rounded text-sm">
          {status.jobs ? JSON.stringify(status.jobs, null, 2) : "No data"}
        </pre>
      </div>

      <JobTable title="All Jobs" data={jobs} refresh={fetchData} />
      <JobTable title="Dead Letter Queue (DLQ)" data={dlq} refresh={fetchData} />

    </div>
  );
}
