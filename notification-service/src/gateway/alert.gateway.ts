import {
  WebSocketGateway,
  WebSocketServer,
  SubscribeMessage,
  OnGatewayConnection,
  OnGatewayDisconnect,
  MessageBody,
  ConnectedSocket,
} from '@nestjs/websockets';
import { Server, Socket } from 'socket.io';
import { Logger } from '@nestjs/common';

export interface AlertPayload {
  sessionId: string;
  studentId: string;
  exerciseType: string;
  errorType: string;
  riskLevel: 'LOW' | 'MEDIUM' | 'HIGH';
  severity: 'WARNING' | 'CRITICAL';
  description: string;
  jointAngle?: number;
  score: number;
  phase: string;
  timestamp: string;
}

/**
 * WebSocket Gateway para entrega de alertas em tempo real.
 *
 * Salas (rooms):
 *   academy:{academyId}  — professor e admin da academia recebem todos os alertas
 *   student:{studentId}  — aluno recebe feedback da sua própria sessão
 *
 * O frontend/app entra na sala após autenticar via JWT.
 */
// CORS_ORIGINS="*" (padrão dev) ou lista separada por vírgula em produção —
// avaliado no carregamento do módulo (variável já definida pelo docker-compose).
const corsOrigins = process.env.CORS_ORIGINS?.split(',').map(o => o.trim()) ?? '*';

@WebSocketGateway({
  cors: { origin: corsOrigins, credentials: corsOrigins !== '*' },
  namespace: '/ws',
  transports: ['websocket', 'polling'],
})
export class AlertGateway implements OnGatewayConnection, OnGatewayDisconnect {
  @WebSocketServer() server: Server;
  private readonly logger = new Logger(AlertGateway.name);

  // Map socketId → { academyId, studentId, role }
  private connections = new Map<string, { academyId: string; studentId?: string; role: string }>();

  handleConnection(client: Socket) {
    this.logger.log(`Cliente conectado: ${client.id}`);
  }

  handleDisconnect(client: Socket) {
    this.connections.delete(client.id);
    this.logger.log(`Cliente desconectado: ${client.id}`);
  }

  /**
   * Professores e admins se inscrevem na sala da academia.
   * Payload: { academyId, userId, role: 'TEACHER' | 'ADMIN' }
   */
  @SubscribeMessage('join_academy')
  handleJoinAcademy(
    @ConnectedSocket() client: Socket,
    @MessageBody() data: { academyId: string; userId: string; role: string },
  ) {
    const room = `academy:${data.academyId}`;
    client.join(room);
    this.connections.set(client.id, { academyId: data.academyId, role: data.role });
    this.logger.log(`${data.role} ${data.userId} entrou na sala ${room}`);
    client.emit('joined', { room, message: `Monitorando academia ${data.academyId}` });
  }

  /**
   * Alunos se inscrevem na sala própria para receber feedback da sessão.
   * Payload: { studentId, academyId }
   */
  @SubscribeMessage('join_student')
  handleJoinStudent(
    @ConnectedSocket() client: Socket,
    @MessageBody() data: { studentId: string; academyId: string },
  ) {
    const room = `student:${data.studentId}`;
    client.join(room);
    client.join(`academy:${data.academyId}`);
    this.connections.set(client.id, { academyId: data.academyId, studentId: data.studentId, role: 'STUDENT' });
    client.emit('joined', { room, message: 'Pronto para receber feedback' });
  }

  /**
   * Entrega o alerta para:
   *   1. Sala da academia (professor vê na dashboard)
   *   2. Sala do aluno (app Android exibe feedback local)
   *
   * Target < 500ms desde a publicação no broker (RNF Sprint 5).
   */
  broadcastAlert(alert: AlertPayload, academyId: string) {
    const t0 = Date.now();
    this.server.to(`academy:${academyId}`).emit('alert', alert);
    this.server.to(`student:${alert.studentId}`).emit('alert', alert);
    this.logger.warn(
      `Alerta broadcast | ${alert.riskLevel} ${alert.errorType} | ` +
      `session=${alert.sessionId} | dispatch=${Date.now() - t0}ms`,
    );
  }

  /**
   * Resultado de análise para o aluno — score e ângulos por frame.
   * Só para a sala do aluno, sem sobrecarregar o dashboard do professor.
   */
  broadcastAnalysis(data: { studentId: string; score: number; phase: string; frameSeq: number }) {
    this.server.to(`student:${data.studentId}`).emit('analysis', data);
  }

  getConnectedCount(): number {
    return this.connections.size;
  }
}
