import { describe, it, expect, beforeEach, vi } from 'vitest';
import { getDb, resetDbForTests } from '../src/db/db';
import {
  extractFirstHttpUrl,
  handleApplyCallback,
  handlePotentialApplyUrl,
  handleProfileCommand,
  handleProfileSetupReply,
  handleSetProfileCommand,
  profileSetupSessions,
  type TelegramBotLike,
} from '../src/bot/handlers';
import type { ApplyEngineClient } from '../src/bot/applyEngineClient';

class FakeBot implements TelegramBotLike {
  messages: Array<{ chatId: number | string; text: string; options?: unknown }> = [];
  callbackAnswers: Array<{ id: string; options?: unknown }> = [];

  async sendMessage(chatId: number | string, text: string, options?: unknown) {
    this.messages.push({ chatId, text, options });
  }

  async answerCallbackQuery(id: string, options?: unknown) {
    this.callbackAnswers.push({ id, options });
  }

  async downloadFile(fileId: string, downloadDir: string) {
    return `${downloadDir}/${fileId}.pdf`;
  }
}

class FakeApplyEngineClient implements ApplyEngineClient {
  startCalls: Array<{ telegramUserId: string; applicationUrl: string }> = [];
  statusCalls: string[] = [];
  openCalls: string[] = [];
  profileGets: string[] = [];
  profileSets: Array<{ telegramUserId: string; profileJson: any }> = [];
  profiles = new Map<string, any>();
  shouldFailStart = false;
  shouldFailGetProfile = false;

  async startDirectApplication(telegramUserId: string, applicationUrl: string) {
    this.startCalls.push({ telegramUserId, applicationUrl });
    if (this.shouldFailStart) {
      throw new Error('apply engine unavailable');
    }
    return {
      application_id: 'app_test_123',
      status: 'opening',
      host_worker_requested: true,
    };
  }

  async getApplicationStatus(applicationId: string) {
    this.statusCalls.push(applicationId);
    return { status: 'opening' };
  }

  async openBrowser(applicationId: string) {
    this.openCalls.push(applicationId);
    return { application_id: applicationId, status: 'opening', host_worker_requested: true };
  }

  async getProfile(telegramUserId: string) {
    this.profileGets.push(telegramUserId);
    if (this.shouldFailGetProfile) {
      throw new Error('Profile not found');
    }
    return this.profiles.get(telegramUserId) || {};
  }

  async setProfile(telegramUserId: string, profileJson: any) {
    this.profileSets.push({ telegramUserId, profileJson });
    this.profiles.set(telegramUserId, profileJson);
  }
}

describe('Telegram bot apply handlers', () => {
  beforeEach(() => {
    process.env.NODE_ENV = 'test';
    resetDbForTests();
    profileSetupSessions.clear();
  });

  it('should extract the first http URL from a message', () => {
    expect(extractFirstHttpUrl('apply https://example.com/jobs/123 please')).toBe('https://example.com/jobs/123');
    expect(extractFirstHttpUrl('not a url')).toBeNull();
  });

  it('should start an application from a direct Telegram URL message', async () => {
    const bot = new FakeBot();
    const client = new FakeApplyEngineClient();

    const handled = await handlePotentialApplyUrl(
      bot,
      { chat: { id: 42 }, text: 'https://example.com/apply' },
      client,
    );

    expect(handled).toBe(true);
    expect(client.startCalls).toEqual([{ telegramUserId: '42', applicationUrl: 'https://example.com/apply' }]);
    expect(bot.messages[0].text).toContain('Application started.');
    expect(bot.messages[0].text).toContain('Opening Chrome on laptop...');

    const db = getDb();
    const user = db.prepare('SELECT id FROM users WHERE telegram_user_id = ?').get('42') as any;
    expect(user.id).toBe('user_42');
  });

  it('should ignore command messages and messages without URLs', async () => {
    const bot = new FakeBot();
    const client = new FakeApplyEngineClient();

    expect(await handlePotentialApplyUrl(bot, { chat: { id: 42 }, text: '/start' }, client)).toBe(false);
    expect(await handlePotentialApplyUrl(bot, { chat: { id: 42 }, text: 'hello' }, client)).toBe(false);
    expect(client.startCalls).toHaveLength(0);
    expect(bot.messages).toHaveLength(0);
  });

  it('should report apply engine failures to the user', async () => {
    const bot = new FakeBot();
    const client = new FakeApplyEngineClient();
    client.shouldFailStart = true;

    const handled = await handlePotentialApplyUrl(
      bot,
      { chat: { id: 42 }, text: 'https://example.com/apply' },
      client,
    );

    expect(handled).toBe(true);
    expect(bot.messages[0].text).toBe('Could not start application: apply engine unavailable');
  });

  it('should handle status callbacks', async () => {
    const bot = new FakeBot();
    const client = new FakeApplyEngineClient();

    const handled = await handleApplyCallback(
      bot,
      { id: 'cb1', data: 'status:app_123', message: { chat: { id: 42 } } },
      client,
    );

    expect(handled).toBe(true);
    expect(client.statusCalls).toEqual(['app_123']);
    expect(bot.messages[0].text).toContain('Status: opening');
    expect(bot.callbackAnswers[0].id).toBe('cb1');
  });

  it('should handle open browser callbacks', async () => {
    const bot = new FakeBot();
    const client = new FakeApplyEngineClient();

    const handled = await handleApplyCallback(
      bot,
      { id: 'cb2', data: 'open_browser:app_123', message: { chat: { id: 42 } } },
      client,
    );

    expect(handled).toBe(true);
    expect(client.openCalls).toEqual(['app_123']);
    expect(bot.messages[0].text).toContain('Browser open requested.');
    expect(bot.callbackAnswers[0].id).toBe('cb2');
  });
  it('should show the saved profile', async () => {
    const bot = new FakeBot();
    const client = new FakeApplyEngineClient();
    client.profiles.set('42', {
      first_name: 'Bhawani',
      email: 'bhawani@example.com',
    });


    await handleProfileCommand(bot, { chat: { id: 42 }, text: '/profile' }, client);

    expect(client.profileGets).toEqual(['42']);
    expect(bot.messages[0].text).toContain('*Your Profile*');
    expect(bot.messages[0].text).toContain('*first_name*: Bhawani');
    expect(bot.messages[0].text).toContain('*email*: bhawani@example.com');
  });

  it('should guide profile setup and save the collected profile', async () => {
    const bot = new FakeBot();
    const client = new FakeApplyEngineClient();

    await handleSetProfileCommand(bot, { chat: { id: 42 }, text: '/setprofile' });
    expect(bot.messages[0].text).toContain('What is your first name?');
    expect(profileSetupSessions.has('42')).toBe(true);

    const answers = [
      'Bhawani',
      'Singh',
      'bhawani@example.com',
      '+911234567890',
      'Bengaluru',
      'https://linkedin.com/in/example',
      'skip',
      'https://example.dev',
    ];

    for (const answer of answers) {
      const handled = await handleProfileSetupReply(bot, { chat: { id: 42 }, text: answer }, client);
      expect(handled).toBe(true);
    }

    expect(profileSetupSessions.has('42')).toBe(false);
    expect(client.profileSets).toHaveLength(1);
    expect(client.profileSets[0]).toEqual({
      telegramUserId: '42',
      profileJson: {
        first_name: 'Bhawani',
        last_name: 'Singh',
        email: 'bhawani@example.com',
        phone: '+911234567890',
        location: 'Bengaluru',
        linkedin_url: 'https://linkedin.com/in/example',
        github_url: '',
        portfolio_url: 'https://example.dev',
      },
    });
    expect(bot.messages.at(-1)?.text).toContain('Profile saved successfully');
  });
});

import { handleDocumentUpload } from '../src/bot/handlers';

describe('Document Upload Handler', () => {
  beforeEach(() => {
    process.env.NODE_ENV = 'test';
    resetDbForTests();
    profileSetupSessions.clear();
  });

  it('should reject non-PDF files', async () => {
    const bot = new FakeBot();
    const handled = await handleDocumentUpload(bot, {
      chat: { id: 42 },
      document: { file_id: 'doc1', mime_type: 'image/png' }
    } as any);

    expect(handled).toBe(true);
    expect(bot.messages[0].text).toContain('Please upload a PDF file');
  });

  it('should save a PDF resume and record it in the DB', async () => {
    const bot = new FakeBot();
    const handled = await handleDocumentUpload(bot, {
      chat: { id: 42 },
      document: { file_id: 'doc123', file_name: 'test_resume.pdf', mime_type: 'application/pdf' }
    } as any);

    expect(handled).toBe(true);
    expect(bot.messages[0].text).toContain('Successfully saved test_resume.pdf');

    const db = getDb();
    const resume = db.prepare('SELECT * FROM resumes WHERE user_id = ?').get('user_42') as any;
    expect(resume).toBeDefined();
    expect(resume.original_filename).toBe('test_resume.pdf');
    expect(resume.file_path).toContain('doc123.pdf');
  });
});

import { handleProvideInputReply, pendingInputSessions } from '../src/bot/handlers';

describe('Provide Input Reply Handler', () => {
  beforeEach(() => {
    pendingInputSessions.clear();
  });

  it('should ignore if there is no pending input session', async () => {
    const bot = { sendMessage: vi.fn() } as any;
    const msg = { chat: { id: 123 }, text: 'My Answer', reply_to_message: {} } as any;
    const client = { provideInput: vi.fn() } as any;

    const result = await handleProvideInputReply(bot, msg, client);
    expect(result).toBe(false);
    expect(client.provideInput).not.toHaveBeenCalled();
  });

  it('should handle reply and call provideInput and openBrowser', async () => {
    pendingInputSessions.set('123', { applicationId: 'app_1', field: 'github_url' });

    const bot = { sendMessage: vi.fn() } as any;
    const msg = { chat: { id: 123 }, text: 'https://github.com/test', reply_to_message: {} } as any;
    const client = { 
      provideInput: vi.fn().mockResolvedValue({}),
      openBrowser: vi.fn().mockResolvedValue({})
    } as any;

    const result = await handleProvideInputReply(bot, msg, client);
    expect(result).toBe(true);
    expect(client.provideInput).toHaveBeenCalledWith('app_1', { github_url: 'https://github.com/test' });
    expect(client.openBrowser).toHaveBeenCalledWith('app_1');
    expect(pendingInputSessions.has('123')).toBe(false);
  });
});
