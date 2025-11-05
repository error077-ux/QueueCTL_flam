import React, { useState } from "react";
import axios from "axios";

export default function JobTable({ title, data, refresh }) {
  const [logText, setLogText] = useState("");
  const [showLog, setShowLog] = useState(false);
  const [currentJob, setCurrentJob] = useState("");

  if (!data || data.length === 0) return null;

  const handleRetry = async (id) => {
    try {
      await axios.post(`http://127.0.0.1:8000/dlq/retry/${id}`);
      alert(`Job ${id} requeued successfully`);
      refresh();
    } catch (err) {
      alert("Failed to retry job: " + err.message);
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm(`Delete job ${id}?`)) return;
    try {
      await axios.delete(`http://127.0.0.1:8000/jobs/${id}`);
      alert(`Job ${id} deleted`);
      refresh();
    } catch (err) {
      alert("Failed to delete job: " + err.message);
    }
  };

  const handleViewLog = async (id) => {
    try {
      const res = await axios.get(`http://127.0.0.1:8000/logs/${id}`);
      setLogText(res.data);
      setCurrentJob(id);
      setShowLog(true);
    } catch (err) {
      alert("No log found for this job.");
    }
  };

  const closeModal = () => {
    setShowLog(false);
    setLogText("");
    setCurrentJob("");
  };

  return (
    <div className="mb-6 bg-white shadow p-4 rounded-lg">
      <h2 className="text-xl font-semibold mb-2">{title}</h2>
      <table className="w-full border border-gray-200 text-sm">
        <thead>
          <tr className="bg-gray-100">
            <th className="p-2 border">ID</th>
            <th className="p-2 border">Command</th>
            <th className="p-2 border">State</th>
            <th className="p-2 border">Attempts</th>
            <th className="p-2 border">Updated</th>
            <th className="p-2 border">Actions</th>
          </tr>
        </thead>
        <tbody>
          {data.map((job) => (
            <tr key={job.id}>
              <td className="border p-2">{job.id}</td>
              <td className="border p-2">{job.command}</td>
              <td className="border p-2">{job.state || "dead"}</td>
              <td className="border p-2">{job.attempts}</td>
              <td className="border p-2">
                {job.updated_at || job.failed_at || "-"}
              </td>
              <td className="border p-2 space-x-2">
                <button
                  onClick={() => handleViewLog(job.id)}
                  className="bg-gray-500 text-white px-2 py-1 rounded hover:bg-gray-600"
                >
                  View Log
                </button>

                {title.includes("DLQ") ? (
                  <button
                    onClick={() => handleRetry(job.id)}
                    className="bg-blue-500 text-white px-2 py-1 rounded hover:bg-blue-600"
                  >
                    Retry
                  </button>
                ) : job.state === "completed" ? (
                  <button
                    onClick={() => handleDelete(job.id)}
                    className="bg-red-500 text-white px-2 py-1 rounded hover:bg-red-600"
                  >
                    Delete
                  </button>
                ) : (
                  "-"
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Log Modal */}
      {showLog && (
        <div className="fixed inset-0 flex items-center justify-center bg-black bg-opacity-50 z-50">
          <div className="bg-white w-3/4 max-h-[80vh] overflow-y-auto p-6 rounded-lg shadow-lg">
            <h3 className="text-xl font-semibold mb-4">
              Log for Job: {currentJob}
            </h3>
            <pre className="bg-gray-100 p-4 rounded text-sm whitespace-pre-wrap">
              {logText}
            </pre>
            <button
              onClick={closeModal}
              className="mt-4 bg-blue-500 text-white px-3 py-1 rounded hover:bg-blue-600"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
