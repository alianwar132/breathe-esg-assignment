import React from "react";
import "./App.css";

const records = [
  {
    id: 1,
    source: "SAP Fuel",
    category: "Scope 1",
    status: "Pending Review",
    emission: "1200 kg CO2e",
  },
  {
    id: 2,
    source: "Utility Electricity",
    category: "Scope 2",
    status: "Approved",
    emission: "890 kg CO2e",
  },
  {
    id: 3,
    source: "Corporate Travel",
    category: "Scope 3",
    status: "Suspicious",
    emission: "450 kg CO2e",
  },
];

function App() {
  return (
    <div style={{ padding: "40px", fontFamily: "Arial" }}>
      <h1>Breathe ESG Review Dashboard</h1>

      <p>
        Review incoming ESG records before audit sign-off.
      </p>

      <table
        border="1"
        cellPadding="12"
        style={{
          width: "100%",
          marginTop: "20px",
          borderCollapse: "collapse",
        }}
      >
        <thead>
          <tr>
            <th>ID</th>
            <th>Source</th>
            <th>Category</th>
            <th>Emission</th>
            <th>Status</th>
            <th>Action</th>
          </tr>
        </thead>

        <tbody>
          {records.map((row) => (
            <tr key={row.id}>
              <td>{row.id}</td>
              <td>{row.source}</td>
              <td>{row.category}</td>
              <td>{row.emission}</td>
              <td>{row.status}</td>

              <td>
                <button>Approve</button>
                <button style={{ marginLeft: "10px" }}>
                  Reject
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default App;
