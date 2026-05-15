import { Controller, Get } from '@nestjs/common';
import { AlertGateway } from './alert.gateway';

@Controller()
export class AlertController {
  constructor(private readonly gateway: AlertGateway) {}

  @Get('/health')
  health() {
    return { status: 'ok', service: 'notification-service', version: '1.0.0' };
  }

  @Get('/api/v1/notify/status')
  status() {
    return {
      status: 'ok',
      connectedClients: this.gateway.getConnectedCount(),
      transport: 'websocket',
    };
  }
}
