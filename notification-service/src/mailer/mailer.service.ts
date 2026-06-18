import { Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import * as nodemailer from 'nodemailer';

export interface SessionReportPayload {
  student_id:     string;
  session_id:     string;
  exercise_type:  string;
  avg_score:      number;
  total_reps:     number;
  alert_count:    number;
  dominant_error: string | null;
  duration_ms:    number;
  started_at:     string;
  ended_at:       string;
}

@Injectable()
export class MailerService {
  private readonly logger = new Logger(MailerService.name);
  private transporter: nodemailer.Transporter;

  constructor(private readonly config: ConfigService) {
    this.transporter = nodemailer.createTransport({
      host:   this.config.get('SMTP_HOST',    'smtp.mailtrap.io'),
      port:   Number(this.config.get('SMTP_PORT', '587')),
      secure: this.config.get('SMTP_SECURE', 'false') === 'true',
      auth: {
        user: this.config.get('SMTP_USER', ''),
        pass: this.config.get('SMTP_PASS', ''),
      },
    });
  }

  async sendSessionReport(to: string, payload: SessionReportPayload): Promise<void> {
    const durationMin = Math.round(payload.duration_ms / 60000);
    const scoreColor  = payload.avg_score >= 80 ? '#22c55e' : payload.avg_score >= 60 ? '#f59e0b' : '#ef4444';
    const exercise    = payload.exercise_type.replace('_', ' ');
    const dominantErr = payload.dominant_error
      ? payload.dominant_error.replace(/_/g, ' ').toLowerCase()
      : 'nenhum';

    const html = `
      <div style="font-family:sans-serif;max-width:520px;margin:0 auto;background:#f9fafb;padding:24px;border-radius:16px">
        <h2 style="color:#111827;margin-bottom:4px">Relatório da sua sessão 💪</h2>
        <p style="color:#6b7280;margin-top:0">${exercise} · ${new Date(payload.started_at).toLocaleDateString('pt-BR')}</p>

        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:20px 0">
          <div style="background:#fff;border-radius:12px;padding:16px;text-align:center;box-shadow:0 1px 3px rgba(0,0,0,.08)">
            <div style="font-size:36px;font-weight:700;color:${scoreColor}">${Math.round(payload.avg_score)}</div>
            <div style="color:#6b7280;font-size:13px">Score médio</div>
          </div>
          <div style="background:#fff;border-radius:12px;padding:16px;text-align:center;box-shadow:0 1px 3px rgba(0,0,0,.08)">
            <div style="font-size:36px;font-weight:700;color:#3b82f6">${payload.total_reps}</div>
            <div style="color:#6b7280;font-size:13px">Repetições</div>
          </div>
          <div style="background:#fff;border-radius:12px;padding:16px;text-align:center;box-shadow:0 1px 3px rgba(0,0,0,.08)">
            <div style="font-size:36px;font-weight:700;color:#8b5cf6">${durationMin}</div>
            <div style="color:#6b7280;font-size:13px">Minutos</div>
          </div>
          <div style="background:#fff;border-radius:12px;padding:16px;text-align:center;box-shadow:0 1px 3px rgba(0,0,0,.08)">
            <div style="font-size:36px;font-weight:700;color:#ef4444">${payload.alert_count}</div>
            <div style="color:#6b7280;font-size:13px">Alertas</div>
          </div>
        </div>

        ${payload.dominant_error ? `
        <div style="background:#fef3c7;border-radius:10px;padding:14px 16px;margin-bottom:16px">
          <strong style="color:#92400e">Principal ponto de atenção:</strong>
          <span style="color:#78350f"> ${dominantErr}</span>
        </div>` : `
        <div style="background:#d1fae5;border-radius:10px;padding:14px 16px;margin-bottom:16px">
          <strong style="color:#065f46">Parabéns!</strong>
          <span style="color:#047857"> Sessão sem erros críticos.</span>
        </div>`}

        <p style="color:#9ca3af;font-size:12px;text-align:center">GymVision · Análise automática de postura</p>
      </div>`;

    try {
      await this.transporter.sendMail({
        from:    this.config.get('SMTP_FROM', 'GymVision <noreply@gymvision.com>'),
        to,
        subject: `Seu treino de hoje: score ${Math.round(payload.avg_score)} — ${exercise}`,
        html,
      });
      this.logger.log(`Relatório enviado para ${to}`);
    } catch (err) {
      this.logger.warn(`Falha ao enviar e-mail para ${to}: ${err.message}`);
    }
  }
}
