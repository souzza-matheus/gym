import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { AlertGateway } from './gateway/alert.gateway';
import { AlertConsumer } from './consumer/alert.consumer';
import { AlertController } from './gateway/alert.controller';

@Module({
  imports: [ConfigModule.forRoot({ isGlobal: true })],
  providers: [AlertGateway, AlertConsumer],
  controllers: [AlertController],
})
export class AppModule {}
