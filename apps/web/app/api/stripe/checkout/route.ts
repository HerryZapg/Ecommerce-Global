import Stripe from "stripe";

export async function POST() {
  const secretKey = process.env.STRIPE_SECRET_KEY;
  if (!secretKey) return new Response("STRIPE_SECRET_KEY missing", { status: 500 });

  const stripe = new Stripe(secretKey, { apiVersion: "2022-11-15" });

  const session = await stripe.checkout.sessions.create({
    mode: "subscription",
    line_items: [
      {
        price_data: {
          currency: "usd",
          product_data: { name: "InventaStock Pro (mensual)" },
          recurring: { interval: "month" },
          unit_amount: 9900,
        },
        quantity: 1,
      },
    ],
    success_url: "http://localhost:3000/admin?checkout=success",
    cancel_url: "http://localhost:3000/admin?checkout=cancel",
  });

  return Response.json({ url: session.url });
}

