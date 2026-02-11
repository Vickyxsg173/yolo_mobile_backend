import { useEffect, useState } from "react";
import axios from "axios";

export default function App() {
  const [imageFile, setImageFile] = useState(null);
  const [data, setData] = useState(null);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    document.body.style.margin = "0";
    document.body.style.background = "#0f172a";
    document.documentElement.style.background = "#0f172a";
  }, []);

  const capture = (e) => {
    setImageFile(e.target.files[0]);
  };

  const upload = async () => {
    if (!imageFile) return alert("Please select an image");

    const fd = new FormData();
    fd.append("file", imageFile);

    try {
      setUploading(true);
      await axios.post("http://192.168.29.210:8000/upload/", fd);
    } catch (err) {
      alert("Upload failed");
      console.error(err);
    } finally {
      setUploading(false);
    }
  };

  useEffect(() => {
    const timer = setInterval(async () => {
      try {
        const res = await axios.get("http://localhost:8000/latest/");
        if (res.data) setData(res.data);
      } catch (err) {
        console.error(err);
      }
    }, 2000);

    return () => clearInterval(timer);
  }, []);

  const isDefective = data?.status === "DEFECTIVE";

  return (
    <div style={styles.page}>
      <h1 style={styles.title}>AI Quality Inspection Dashboard</h1>
      <p style={styles.subtitle}>
        Real‑time screen & packaging defect detection
      </p>

      <div style={styles.kpiGrid}>
        <div style={styles.kpiCard}>
          <h3>Total Inspected</h3>
          <p style={styles.kpiValue}>{data?.stats?.total || 0}</p>
        </div>
        <div style={styles.kpiCard}>
          <h3>Defective</h3>
          <p style={{ ...styles.kpiValue, color: "#ef4444" }}>
            {data?.stats?.defective || 0}
          </p>
        </div>
        <div style={styles.kpiCard}>
          <h3>Pass Rate</h3>
          <p style={styles.kpiValue}>
            {data?.stats?.total
              ? (
                  ((data.stats.total - data.stats.defective) /
                    data.stats.total) *
                  100
                ).toFixed(1)
              : 0}
            %
          </p>
        </div>
      </div>

      <div style={styles.mainGrid}>
        <div style={styles.card}>
          <h2>Capture / Upload</h2>
          <input
            type="file"
            accept="image/*"
            capture="environment"
            onChange={capture}
          />
          <br /><br />
          <button
            onClick={upload}
            disabled={uploading}
            style={styles.button}
          >
            {uploading ? "Uploading..." : "Upload Image"}
          </button>
          {imageFile && (
            <p style={styles.muted}>Selected: {imageFile.name}</p>
          )}
        </div>

        <div style={styles.card}>
          <h2>Inspection Result</h2>
          {!data ? (
            <p style={styles.muted}>Waiting for inspection…</p>
          ) : (
            <>
              <div
                style={{
                  ...styles.status,
                  background: isDefective ? "#ef4444" : "#22c55e",
                }}
              >
                {data.status}
              </div>
              <p>Confidence: {(data.confidence * 100).toFixed(2)}%</p>
              <p>Detected Defects: {data.defects?.length || 0}</p>
              <p>Latency: {data.latency || "--"} ms</p>
            </>
          )}
        </div>

        <div style={{ ...styles.card, gridColumn: "span 2" }}>
          <h2>Processed Image</h2>
          {!data ? (
            <p style={styles.muted}>No image processed yet</p>
          ) : (
            <img
              src={`http://localhost:8000/uploads/${data.image}?t=${Date.now()}`}
              alt="Result"
              style={styles.image}
            />
          )}
        </div>
      </div>
    </div>
  );
}

const styles = {
  page: {
    minHeight: "100vh",
    background: "#0f172a",
    color: "#e5e7eb",
    padding: 24,
    fontFamily: "Inter, system-ui, sans-serif",
  },
  title: {
    marginBottom: 4,
  },
  subtitle: {
    marginBottom: 24,
    color: "#94a3b8",
  },
  kpiGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
    gap: 16,
    marginBottom: 24,
  },
  kpiCard: {
    background: "#020617",
    border: "1px solid #1e293b",
    borderRadius: 12,
    padding: 16,
  },
  kpiValue: {
    fontSize: 28,
    fontWeight: 700,
  },
  mainGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
    gap: 20,
  },
  card: {
    background: "#020617",
    border: "1px solid #1e293b",
    borderRadius: 14,
    padding: 18,
  },
  button: {
    background: "#2563eb",
    border: "none",
    color: "#fff",
    padding: "10px 14px",
    borderRadius: 10,
    cursor: "pointer",
    fontWeight: 600,
  },
  muted: {
    color: "#94a3b8",
    fontSize: 13,
  },
  status: {
    display: "inline-block",
    padding: "6px 14px",
    borderRadius: 999,
    color: "#fff",
    fontWeight: 700,
    marginBottom: 10,
  },
  image: {
    width: "100%",
    borderRadius: 12,
    border: "1px solid #1e293b",
  },
};