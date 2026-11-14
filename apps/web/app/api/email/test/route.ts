import sgMail from "@sendgrid/mail";

export async function POST(req: Request) {
  const apiKey = process.env.SENDGRID_API_KEY;
  if (!apiKey) return new Response("SENDGRID_API_KEY missing", { status: 500 });

  const { to } = (await req.json()) as { to?: string };
  if (!to) return new Response("to required", { status: 400 });

  sgMail.setApiKey(apiKey);
  await sgMail.send({
    to,
    from: "no-reply@inventastock.local",
    subject: "InventaStock Pro — email de prueba",
    text: "Hola! Este es un email de prueba del MVP.",
  });

  return Response.json({ ok: true });
}

