import { Injectable, OnModuleInit, OnModuleDestroy, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import * as amqp from 'amqplib';
import { AlertGateway, AlertPayload } from '../gateway/alert.gateway';
import { MailerService } from '../mailer/mailer.service';

/**
 * Consome gym.alert.created do RabbitMQ e entrega via WebSocket.
 * Latência target: < 500ms end-to-end (da publicação até o professor ver).
 */
@Injectable()
export class AlertConsumer implements OnModuleInit, OnModuleDestroy {
  private readonly logger = new Logger(AlertConsumer.name);
  private connection: amqp.ChannelModel | null = null;
  private channel: amqp.Channel | null = null;

  constructor(
    private readonly gateway: AlertGateway,
    private readonly config: ConfigService,
    private readonly mailer: MailerService,
  ) {}

  async onModuleInit() {
    await this.connect();
  }

  async onModuleDestroy() {
    try {
      await this.channel?.close();
      await this.connection?.close();
    } catch {}
  }

  private async connect(retries = 5) {
    const url = this.config.get<string>('RABBITMQ_URL', 'amqp://gymvision:gymvision123@rabbitmq:5672/');

    for (let i = 0; i < retries; i++) {
      try {
        this.connection = await amqp.connect(url);
        this.channel = await this.connection.createChannel();
        // Filas dedicadas: cada serviço tem a sua própria fila vinculada ao mesmo
        // exchange, garantindo que todos recebam uma cópia de cada mensagem (fan-out).
        await this.channel.assertQueue('notify.alert.created',   { durable: true });
        await this.channel.assertQueue('notify.exercise.result',  { durable: true });
        await this.channel.assertQueue('notify.session.ended',    { durable: true });
        this.channel.prefetch(10);
        this.startConsuming();
        this.logger.log('RabbitMQ conectado. Consumindo alertas...');
        return;
      } catch (err) {
        this.logger.warn(`RabbitMQ tentativa ${i + 1}/${retries}: ${err.message}`);
        await new Promise(r => setTimeout(r, 3000));
      }
    }
    this.logger.error('Não foi possível conectar ao RabbitMQ após múltiplas tentativas.');
  }

  private startConsuming() {
    // ── Alertas → WebSocket para professor e aluno ────────────────────────
    this.channel!.consume('notify.alert.created', (msg) => {
      if (!msg) return;
      try {
        const payload = JSON.parse(msg.content.toString());
        const data = payload.data;

        const alert: AlertPayload = {
          sessionId:    data.session_id,
          studentId:    data.student_id,
          exerciseType: data.exercise_type,
          errorType:    data.error_type,
          riskLevel:    data.risk_level,
          severity:     data.severity ?? 'WARNING',
          description:  data.description,
          jointAngle:   data.joint_angle,
          score:        data.score,
          phase:        data.phase,
          timestamp:    payload.timestamp,
        };

        // academyId precisa vir no payload ou ser consultado —
        // por simplicidade o Pose Service inclui academy_id no evento
        const academyId = data.academy_id ?? 'unknown';
        this.gateway.broadcastAlert(alert, academyId);
        this.channel!.ack(msg);
      } catch (err) {
        this.logger.error(`Erro ao processar alerta: ${err.message}`);
        this.channel!.nack(msg, false, false);
      }
    });

    // ── Resultados de análise → feedback de score para o aluno ───────────
    this.channel!.consume('notify.exercise.result', (msg) => {
      if (!msg) return;
      try {
        const payload = JSON.parse(msg.content.toString());
        const data = payload.data;
        this.gateway.broadcastAnalysis({
          studentId: data.student_id,
          score:     data.score,
          phase:     data.phase,
          frameSeq:  data.frame_seq,
        });
        this.channel!.ack(msg);
      } catch (err) {
        this.logger.error(`Erro ao processar result: ${err.message}`);
        this.channel!.nack(msg, false, false);
      }
    });

    // ── Fim de sessão → e-mail de relatório para o aluno ─────────────────
    this.channel!.consume('notify.session.ended', (msg) => {
      if (!msg) return;
      try {
        const payload = JSON.parse(msg.content.toString());
        const data    = payload.data;
        const to      = data.student_email ?? data.student_id;
        if (to && to.includes('@')) {
          this.mailer.sendSessionReport(to, data).catch(() => {});
        }
        this.channel!.ack(msg);
      } catch (err) {
        this.logger.error(`Erro ao processar session.ended: ${err.message}`);
        this.channel!.nack(msg, false, false);
      }
    });
  }
}
