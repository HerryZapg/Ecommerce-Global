import { prisma } from "@/lib/prisma";

export async function GET() {
  const warehouses = await prisma.warehouse.findMany({ orderBy: { id: "desc" } });
  return Response.json(warehouses);
}

export async function POST(req: Request) {
  const body = (await req.json()) as { name?: string };
  if (!body.name) return new Response("name required", { status: 400 });

  const wh = await prisma.warehouse.create({ data: { name: body.name } });
  return Response.json(wh, { status: 201 });
}

