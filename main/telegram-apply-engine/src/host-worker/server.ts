import express from 'express';
import dotenv from 'dotenv';
import { createServer } from 'http';
import { HostWorkerSessionManager } from './sessionManager';

dotenv.config();

export function createHostWorkerApp(manager = new HostWorkerSessionManager()) {
  const app = express();
  app.use(express.json());

  app.get('/health', (_req, res) => {
    res.json({
      ok: true,
      service: 'host-chrome-worker',
      chrome_channel: process.env.CHROME_CHANNEL || 'chrome',
      headless: process.env.HOST_WORKER_HEADLESS === 'true',
      sessions: manager.listSessions().length,
    });
  });

  app.get('/sessions', (_req, res) => {
    res.json({ sessions: manager.listSessions() });
  });

  app.post('/sessions', async (req, res) => {
    const { application_id, url, profile_id, headless } = req.body || {};

    if (!application_id || typeof application_id !== 'string') {
      return res.status(400).json({ error: 'Missing application_id' });
    }

    if (url && typeof url !== 'string') {
      return res.status(400).json({ error: 'url must be a string' });
    }

    try {
      const session = await manager.createSession({ application_id, url, profile_id, headless });
      res.status(201).json({ session });
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : String(error) });
    }
  });

  app.get('/sessions/:id/status', (req, res) => {
    const session = manager.getSession(req.params.id);
    if (!session) {
      return res.status(404).json({ error: 'Session not found' });
    }
    res.json({ session });
  });

  app.get('/sessions/:id/inspect', async (req, res) => {
    try {
      const result = await manager.inspectSession(req.params.id);
      res.json(result);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      const status = message.startsWith('Session not found') ? 404 : 500;
      res.status(status).json({ error: message });
    }
  });

  app.get('/sessions/:id/screenshot', async (req, res) => {
    try {
      const screenshot = await manager.screenshotSession(req.params.id);
      res.type('png').send(screenshot);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      const status = message.startsWith('Session not found') ? 404 : 500;
      res.status(status).json({ error: message });
    }
  });

  app.post('/sessions/:id/navigate', async (req, res) => {
    const { url } = req.body || {};

    if (!url || typeof url !== 'string') {
      return res.status(400).json({ error: 'Missing url' });
    }

    try {
      const session = await manager.navigate(req.params.id, url);
      res.json({ session });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      const status = message.startsWith('Session not found') ? 404 : 500;
      res.status(status).json({ error: message });
    }
  });

  app.post('/sessions/:id/fill', async (req, res) => {
    const { profile, resume_path } = req.body || {};

    if (!profile || typeof profile !== 'object' || Array.isArray(profile)) {
      return res.status(400).json({ error: 'Missing profile object' });
    }

    try {
      const result = await manager.fillSession(req.params.id, profile, resume_path);
      res.json(result);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      const status = message.startsWith('Session not found') ? 404 : 500;
      res.status(status).json({ error: message });
    }
  });

  app.post('/sessions/:id/submit', async (req, res) => {
    try {
      const result = await manager.submitSession(req.params.id);
      res.json(result);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      const status = message.startsWith('Session not found') ? 404 : 500;
      res.status(status).json({ error: message });
    }
  });

  app.post('/sessions/:id/verify', async (req, res) => {
    const { code } = req.body || {};

    if (!code || typeof code !== 'string') {
      return res.status(400).json({ error: 'Missing code' });
    }

    try {
      const result = await manager.verifySession(req.params.id, code);
      res.json(result);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      const status = message.startsWith('Session not found') ? 404 : 500;
      res.status(status).json({ error: message });
    }
  });

  app.post('/sessions/:id/click', async (req, res) => {
    const { selector } = req.body || {};
    if (!selector || typeof selector !== 'string') {
      return res.status(400).json({ error: 'Missing selector' });
    }
    try {
      const result = await manager.clickElement(req.params.id, selector);
      res.json(result);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      const status = message.startsWith('Session not found') ? 404 : 500;
      res.status(status).json({ error: message });
    }
  });

  app.post('/sessions/:id/type', async (req, res) => {
    const { selector, text } = req.body || {};
    if (!selector || typeof selector !== 'string') {
      return res.status(400).json({ error: 'Missing selector' });
    }
    if (typeof text !== 'string') {
      return res.status(400).json({ error: 'Missing text' });
    }
    try {
      const result = await manager.typeElement(req.params.id, selector, text);
      res.json(result);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      const status = message.startsWith('Session not found') ? 404 : 500;
      res.status(status).json({ error: message });
    }
  });

  app.post('/sessions/:id/clickAt', async (req, res) => {
    const { x, y } = req.body || {};
    if (typeof x !== 'number' || typeof y !== 'number') {
      return res.status(400).json({ error: 'Missing numeric x and y' });
    }
    try {
      const result = await manager.clickCoordinate(req.params.id, x, y);
      res.json(result);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      const status = message.startsWith('Session not found') ? 404 : 500;
      res.status(status).json({ error: message });
    }
  });

  app.post('/sessions/:id/typeAt', async (req, res) => {
    const { x, y, text } = req.body || {};
    if (typeof x !== 'number' || typeof y !== 'number') {
      return res.status(400).json({ error: 'Missing numeric x and y' });
    }
    if (typeof text !== 'string') {
      return res.status(400).json({ error: 'Missing text' });
    }
    try {
      const result = await manager.typeCoordinate(req.params.id, x, y, text);
      res.json(result);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      const status = message.startsWith('Session not found') ? 404 : 500;
      res.status(status).json({ error: message });
    }
  });

  app.post('/sessions/:id/evaluate', async (req, res) => {
    const { script } = req.body || {};
    if (!script || typeof script !== 'string') {
      return res.status(400).json({ error: 'Missing script' });
    }
    try {
      const result = await manager.evaluateScript(req.params.id, script);
      res.json(result);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      const status = message.startsWith('Session not found') ? 404 : 500;
      res.status(status).json({ error: message });
    }
  });

  app.post('/sessions/:id/close', async (req, res) => {
    try {
      const session = await manager.closeSession(req.params.id);
      res.json({ session });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      const status = message.startsWith('Session not found') ? 404 : 500;
      res.status(status).json({ error: message });
    }
  });

  return { app, manager };
}

export function startHostWorker() {
  const port = Number(process.env.HOST_WORKER_PORT || 4555);
  const { app, manager } = createHostWorkerApp();
  const server = createServer(app);

  server.on('error', (error: any) => {
    if (error.code === 'EADDRINUSE') {
      console.error(`\n[ERROR] Host Worker port ${port} is already in use.`);
      console.error(`Please free the port or change the HOST_WORKER_PORT environment variable in your .env file.\n`);
      process.exit(1);
    }
    throw error;
  });

  const serverInstance = server.listen(port, '127.0.0.1', () => {
    console.log(`Host Chrome Worker running on http://127.0.0.1:${port}`);
  });

  const shutdown = async () => {
    await manager.closeAll();
    server.close(() => process.exit(0));
  };

  process.on('SIGINT', shutdown);
  process.on('SIGTERM', shutdown);

  return server;
}

if (require.main === module) {
  startHostWorker();
}
