import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import net from 'net';

describe('Server Startup Validation', () => {
  let exitSpy: ReturnType<typeof vi.spyOn>;
  let errorSpy: ReturnType<typeof vi.spyOn>;
  let warnSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    exitSpy = vi.spyOn(process, 'exit').mockImplementation((() => {
      throw new Error('process.exit called');
    }) as any);
    errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
    
    vi.resetModules();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('should fail fast if bot token is missing in production', async () => {
    process.env.NODE_ENV = 'production';
    process.env.TELEGRAM_BOT_TOKEN = '';

    await expect(async () => {
      await import('../src/bot/bot');
    }).rejects.toThrow('process.exit called');

    expect(errorSpy).toHaveBeenCalledWith(expect.stringContaining('TELEGRAM_BOT_TOKEN is not set'));
  });

  it('should warn if HOST_WORKER_URL is missing in production', async () => {
    process.env.NODE_ENV = 'production';
    process.env.HOST_WORKER_URL = '';
    process.env.PORT = '0'; // Random port

    const serverModule = await import('../src/server');
    expect(warnSpy).toHaveBeenCalledWith(expect.stringContaining('HOST_WORKER_URL is not set'));
    
    // Cleanup the started server if any
    if (serverModule.default) {
       // It didn't start the server because require.main !== module
    }
  });

  it('should handle EADDRINUSE for backend server', async () => {
    process.env.PORT = '41236';
    const blocker = net.createServer();
    await new Promise<void>(resolve => blocker.listen(41236, () => resolve()));

    const { startServer } = await import('../src/server');
    
    await new Promise<void>((resolve) => {
      exitSpy.mockImplementation(() => resolve() as any);
      startServer();
    });

    expect(errorSpy).toHaveBeenCalledWith(expect.stringContaining('is already in use'));
    
    blocker.close();
  });

  it('should handle EADDRINUSE for host worker server', async () => {
    process.env.HOST_WORKER_PORT = '41237';
    const blocker = net.createServer();
    await new Promise<void>(resolve => blocker.listen(41237, '127.0.0.1', () => resolve()));

    const { startHostWorker } = await import('../src/host-worker/server');
    
    await new Promise<void>((resolve) => {
      exitSpy.mockImplementation(() => resolve() as any);
      startHostWorker();
    });

    expect(errorSpy).toHaveBeenCalledWith(expect.stringContaining('is already in use'));

    blocker.close();
  });
});
