import Link from "next/link";

export default function AdminHomePage() {
  return (
    <main style={{ padding: 24 }}>
      <h1>Admin — InventaStock Pro</h1>
      <ul>
        <li>
          <Link href="/admin/skus">SKUs</Link>
        </li>
        <li>
          <Link href="/admin/warehouses">Almacenes</Link>
        </li>
        <li>
          <Link href="/admin/movements">Movimientos</Link>
        </li>
        <li>
          <Link href="/admin/dashboard">Dashboard</Link>
        </li>
        <li>
          <Link href="/admin/chat">Chat IA</Link>
        </li>
      </ul>
    </main>
  );
}

