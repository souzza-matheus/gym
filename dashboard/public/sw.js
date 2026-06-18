self.addEventListener('push', (event) => {
  const data = event.data?.json() ?? {};
  const title = data.title ?? 'GymVision — Alerta';
  const options = {
    body:    data.body ?? 'Novo alerta de postura detectado.',
    icon:    '/favicon.ico',
    badge:   '/favicon.ico',
    tag:     data.tag ?? 'gymvision-alert',
    data:    { url: data.url ?? '/' },
    actions: [{ action: 'view', title: 'Ver dashboard' }],
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil(clients.openWindow(event.notification.data?.url ?? '/'));
});
