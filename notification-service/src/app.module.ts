import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { AlertGateway } from './gateway/alert.gateway';
import { AlertConsumer } from './consumer/alert.consumer';
import { AlertController } from './gateway/alert.controller';
import { MailerService } from './mailer/mailer.service';

@Module({
  imports: [ConfigModule.forRoot({ isGlobal: true })],
  providers: [AlertGateway, AlertConsumer, MailerService],
  controllers: [AlertController],
})
export class AppModule {}
