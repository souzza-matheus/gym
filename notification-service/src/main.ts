import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);
  app.enableCors({ origin: '*' });
  await app.listen(8085);
  console.log('GymVision Notification Service rodando na porta 8085');
}
bootstrap();
