# InventaStock Pro (MVP)

Monorepo Turbo:

- `apps/web`: Next.js 15 (admin + storefront MVP)
- `backend/`: Spring Boot 2.7 (API REST + Kafka consumer + Stripe webhooks)

## Desarrollo

1. Copia `.env.example` a `.env` y completa valores.
2. Frontend:
   ```bash
   cd apps/web
   npm run dev
   ```
3. Backend:
   ```bash
   cd backend
   mvn spring-boot:run
   ```

