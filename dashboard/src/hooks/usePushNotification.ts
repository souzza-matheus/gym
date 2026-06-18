import { useEffect, useState } from 'react';

export function usePushNotification() {
  const [supported, setSupported] = useState(false);
  const [permission, setPermission] = useState<NotificationPermission>('default');

  useEffect(() => {
    setSupported('serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window);
    if ('Notification' in window) setPermission(Notification.permission);
  }, []);

  const register = async (): Promise<boolean> => {
    if (!supported) return false;
    try {
      const reg = await navigator.serviceWorker.register('/sw.js');
      await navigator.serviceWorker.ready;
      const result = await Notification.requestPermission();
      setPermission(result);
      if (result !== 'granted') return false;
      // Registra o service worker mas não precisa de VAPID keys para notificações locais
      // (as notificações são disparadas diretamente pelo hook quando chega alerta via WebSocket)
      console.log('[SW] Service worker registrado:', reg.scope);
      return true;
    } catch (err) {
      console.warn('[SW] Falha ao registrar service worker:', err);
      return false;
    }
  };

  const notify = (title: string, body: string, tag?: string) => {
    if (permission !== 'granted') return;
    if (document.visibilityState === 'visible') return; // só notifica se aba estiver em background
    navigator.serviceWorker.ready.then(reg => {
      reg.showNotification(title, {
        body,
        icon:  '/favicon.ico',
        badge: '/favicon.ico',
        tag:   tag ?? 'gymvision-alert',
      });
    }).catch(() => {
      new Notification(title, { body });
    });
  };

  return { supported, permission, register, notify };
}
