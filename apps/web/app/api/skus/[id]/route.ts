import { prisma } from "@/lib/prisma";

export async function PUT(req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id: idParam } = await ctx.params;
  const id = Number(idParam);
  if (!Number.isFinite(id)) return new Response("invalid id", { status: 400 });

  const body = (await req.json()) as { code?: string; name?: string };
  const sku = await prisma.sku.update({
    where: { id },
    data: { code: body.code, name: body.name },
  });
  return Response.json(sku);
}

export async function DELETE(_req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id: idParam } = await ctx.params;
  const id = Number(idParam);
  if (!Number.isFinite(id)) return new Response("invalid id", { status: 400 });

  await prisma.sku.delete({ where: { id } });
  return new Response(null, { status: 204 });
}

