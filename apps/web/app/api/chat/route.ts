import { OpenAIStream, StreamingTextResponse } from "ai";
import OpenAI from "openai";
import { Redis } from "@upstash/redis";

export async function POST(req: Request) {
  const { message } = (await req.json()) as { message?: string };
  const content = message ?? "Stock bajo en SKU-99";

  const openai = new OpenAI();
  const response = await openai.chat.completions.create({
    model: "gpt-4",
    stream: true,
    messages: [{ role: "user", content }],
  });

  const redis = Redis.fromEnv();
  await redis.zadd("admin-chat", { score: Date.now(), member: content });

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const stream = OpenAIStream(response as any);
  return new StreamingTextResponse(stream);
}

