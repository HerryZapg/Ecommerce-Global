import { prisma } from "@/lib/prisma";

export async function GET() {
  const skus = await prisma.sku.findMany({ orderBy: { id: "desc" } });
  return Response.json(skus);
}

export async function POST(req: Request) {
  const body = (await req.json()) as { code?: string; name?: string };
  if (!body.code || !body.name) return new Response("code and name required", { status: 400 });

  const sku = await prisma.sku.create({
    data: { code: body.code, name: body.name },
  });
  return Response.json(sku, { status: 201 });
}

