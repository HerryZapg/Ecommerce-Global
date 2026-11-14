import { prisma } from "@/lib/prisma";

export async function GET() {
  const movements = await prisma.inventoryMovement.findMany({ orderBy: { id: "desc" } });
  return Response.json(movements);
}

export async function POST(req: Request) {
  const body = (await req.json()) as {
    skuCode?: string;
    warehouseId?: number;
    delta?: number;
    reason?: string;
  };

  if (!body.skuCode || typeof body.warehouseId !== "number" || typeof body.delta !== "number") {
    return new Response("skuCode, warehouseId, delta required", { status: 400 });
  }

  const movement = await prisma.inventoryMovement.create({
    data: {
      skuCode: body.skuCode,
      warehouseId: body.warehouseId,
      delta: body.delta,
      reason: body.reason,
    },
  });
  return Response.json(movement, { status: 201 });
}

