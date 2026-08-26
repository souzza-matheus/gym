import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';

// CORS_ORIGINS="*" (padrão dev) ou lista separada por vírgula em produção —
// permite app Android, dashboard web e personal remoto em redes diferentes.
const corsOrigins = process.env.CORS_ORIGINS?.split(',').map(o => o.trim()) ?? '*';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);
  app.enableCors({
    origin: corsOrigins,
    methods: ['GET', 'POST', 'OPTIONS'],
    allowedHeaders: ['Content-Type', 'Authorization'],
    credentials: corsOrigins !== '*',
  });
  await app.listen(8085);
  console.log('GymVision Notification Service rodando na porta 8085');
}
bootstrap();
