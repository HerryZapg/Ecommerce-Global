"use client";

import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

type Movement = { delta: number };

export default function DashboardPage() {
  const [data, setData] = useState<{ name: string; value: number }[]>([]);

  useEffect(() => {
    (async () => {
      const res = await fetch("/api/movements");
      const movements = (await res.json()) as Movement[];
      const total = movements.reduce((acc, m) => acc + (m.delta ?? 0), 0);
      setData([{ name: "Movimientos (Δ)", value: total }]);
    })();
  }, []);

  return (
    <main style={{ padding: 24 }}>
      <h1>Dashboard</h1>
      <div style={{ width: "100%", height: 320 }}>
        <ResponsiveContainer>
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" />
            <YAxis />
            <Tooltip />
            <Bar dataKey="value" fill="#2563eb" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </main>
  );
}

