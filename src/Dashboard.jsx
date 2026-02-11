import { useEffect, useState } from "react";
import axios from "axios";

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    const timer = setInterval(async () => {
      try {
        const res = await axios.get("http://localhost:8000/latest/");
        if (res.data) {
          setData(res.data);
          setError(null);
        }
      } catch (err) {
        setError("Backend not reachable");
        console.error(err);
      }
    }, 2000);

    return () => clearInterval(timer);
  }, []);

  if (error) {
    return <h3 style={{ color: "red" }}>{error}</h3>;
  }

  if (!data) {
    return <h3>Waiting for image upload…</h3>;
  }

  return (
    <div style={{ padding: 20 }}>
      <h2>📊 Inspection Dashboard</h2>

      <p>
        <strong>Status:</strong> {data.status}
      </p>
      <p>
        <strong>Confidence:</strong> {data.confidence}
      </p>

      <img
        src={`http://localhost:8000/uploads/${data.image}?t=${Date.now()}`}
        width="320"
        alt="Latest uploaded"
        style={{ border: "1px solid #ccc", borderRadius: 8 }}
      />
    </div>
  );
}