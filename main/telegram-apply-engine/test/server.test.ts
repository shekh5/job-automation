import { describe, it, expect, beforeEach } from 'vitest';
import request from 'supertest';
import fs from 'fs';
import os from 'os';
import path from 'path';
import app from '../src/server';
import { getDb, resetDbForTests } from '../src/db/db';
import { setHostWorkerClientForTests, type HostWorkerClient } from '../src/apply/hostWorkerClient';

describe('Backend API', () => {
  beforeEach(() => {
    process.env.NODE_ENV = 'test';
    setHostWorkerClientForTests(null);
    const db = resetDbForTests();
    db.prepare('INSERT OR IGNORE INTO users (id, telegram_user_id) VALUES (?, ?)').run('u1', 'test_tg_id');
    db.prepare('INSERT OR IGNORE INTO jobs (id, company, title, application_url) VALUES (?, ?, ?, ?)').run('job1', 'Test Co', 'Dev', 'http://test.com');
    db.prepare('INSERT OR IGNORE INTO jobs (id, company, title, application_url) VALUES (?, ?, ?, ?)').run('job2', 'Test Co', 'Dev 2', 'http://test2.com');
  });

  it('should start an application process', async () => {
    const res = await request(app)
      .post('/api/apply/start')
      .send({ telegram_user_id: 'test_tg_id', job_id: 'job1' });
    
    expect(res.status).toBe(200);
    expect(res.body.application_id).toBeDefined();
    expect(res.body.status).toBe('created');
    expect(res.body.host_worker_requested).toBe(false);
  });

  it('should fetch application status', async () => {
    const startRes = await request(app)
      .post('/api/apply/start')
      .send({ telegram_user_id: 'test_tg_id', job_id: 'job2' });

    expect(startRes.status).toBe(200);

    const statusRes = await request(app).get(`/api/apply/${startRes.body.application_id}/status`);
    expect(statusRes.status).toBe(200);
    expect(statusRes.body.status).toBe('created');
  });

  it('should fetch application events timeline', async () => {
    const startRes = await request(app)
      .post('/api/apply/start')
      .send({ telegram_user_id: 'test_tg_id', job_id: 'job2' });

    const appId = startRes.body.application_id;
    const eventsRes = await request(app).get(`/api/applications/${appId}/events`);
    
    expect(eventsRes.status).toBe(200);
    expect(eventsRes.body.application_id).toBe(appId);
    expect(eventsRes.body.events).toBeInstanceOf(Array);
    expect(eventsRes.body.events.length).toBeGreaterThan(0);
    expect(eventsRes.body.events[0].type).toBe('application_started');
    expect(eventsRes.body.events[0].data).toEqual({ job_id: 'job2', application_url: 'http://test2.com' });
  });

  it('should create a direct URL job and request the host worker when configured', async () => {
    const calls: unknown[] = [];
    const mockClient: HostWorkerClient = {
      async createSession(input) {
        calls.push(input);
        return { session: { status: 'ready' } };
      },
      async fillSession() {
        throw new Error('not used');
      },
    };
    setHostWorkerClientForTests(mockClient);

    const res = await request(app)
      .post('/api/apply/start')
      .send({ telegram_user_id: 'test_tg_id', application_url: 'https://example.com/apply' });

    expect(res.status).toBe(200);
    expect(res.body.status).toBe('opening');
    expect(res.body.host_worker_requested).toBe(true);
    expect(calls).toHaveLength(1);
    expect(calls[0]).toMatchObject({
      application_id: res.body.application_id,
      url: 'https://example.com/apply',
      profile_id: 'u1',
    });

    const db = getDb();
    const appRecord = db.prepare('SELECT status, current_step FROM applications WHERE id = ?').get(res.body.application_id) as any;
    expect(appRecord.status).toBe('opening');
    expect(appRecord.current_step).toBe('host_worker_session_requested');

    const event = db.prepare(`
      SELECT event_type FROM application_events
      WHERE application_id = ? AND event_type = ?
    `).get(res.body.application_id, 'host_worker_session_requested') as any;
    expect(event.event_type).toBe('host_worker_session_requested');
  });

  it('should auto-register users for direct URL smoke starts', async () => {
    const calls: unknown[] = [];
    const mockClient: HostWorkerClient = {
      async createSession(input) {
        calls.push(input);
        return { session: { status: 'ready' } };
      },
      async fillSession() {
        throw new Error('not used');
      },
    };
    setHostWorkerClientForTests(mockClient);

    const res = await request(app)
      .post('/api/apply/start')
      .send({ telegram_user_id: 'new_smoke_user', application_url: 'https://example.com/smoke' });

    expect(res.status).toBe(200);
    expect(res.body.status).toBe('opening');

    const db = getDb();
    const user = db.prepare('SELECT id FROM users WHERE telegram_user_id = ?').get('new_smoke_user') as any;
    expect(user.id).toBe('user_new_smoke_user');
    expect(calls[0]).toMatchObject({
      application_id: res.body.application_id,
      url: 'https://example.com/smoke',
      profile_id: 'user_new_smoke_user',
    });
  });

  it('should mark the application failed when host worker request fails', async () => {
    const mockClient: HostWorkerClient = {
      async createSession() {
        throw new Error('worker unavailable');
      },
      async fillSession() {
        throw new Error('not used');
      },
    };
    setHostWorkerClientForTests(mockClient);

    const res = await request(app)
      .post('/api/apply/start')
      .send({ telegram_user_id: 'test_tg_id', job_id: 'job1' });

    expect(res.status).toBe(502);
    expect(res.body.status).toBe('failed');
    expect(res.body.error).toBe('worker unavailable');

    const db = getDb();
    const appRecord = db.prepare('SELECT status, current_step FROM applications WHERE id = ?').get(res.body.application_id) as any;
    expect(appRecord.status).toBe('failed');
    expect(appRecord.current_step).toBe('host_worker_failed');
  });

  it('should retry opening an existing application in the host worker', async () => {
    const calls: unknown[] = [];
    const mockClient: HostWorkerClient = {
      async createSession(input) {
        calls.push(input);
        return { session: { status: 'ready' } };
      },
      async fillSession() {
        throw new Error('not used');
      },
    };

    const startRes = await request(app)
      .post('/api/apply/start')
      .send({ telegram_user_id: 'test_tg_id', job_id: 'job1' });

    expect(startRes.status).toBe(200);
    setHostWorkerClientForTests(mockClient);

    const retryRes = await request(app).post(`/api/apply/${startRes.body.application_id}/open-browser`);

    expect(retryRes.status).toBe(200);
    expect(retryRes.body.status).toBe('opening');
    expect(calls).toHaveLength(1);
    expect(calls[0]).toMatchObject({
      application_id: startRes.body.application_id,
      url: 'http://test.com',
      profile_id: 'u1',
    });
  });

  it('should reject invalid direct application URLs', async () => {
    const res = await request(app)
      .post('/api/apply/start')
      .send({ telegram_user_id: 'test_tg_id', application_url: 'javascript:alert(1)' });

    expect(res.status).toBe(400);
    expect(res.body.error).toBe('application_url must be an http or https URL');
  });

  it('should fill an application with the saved user profile', async () => {
    const db = getDb();
    db.prepare('INSERT INTO user_profiles (user_id, profile_json) VALUES (?, ?)').run(
      'u1',
      JSON.stringify({
        first_name: 'Bhawani',
        last_name: 'Singh',
        email: 'bhawani@example.com',
        phone: '+911234567890',
      }),
    );

    const startRes = await request(app)
      .post('/api/apply/start')
      .send({ telegram_user_id: 'test_tg_id', job_id: 'job1' });
    expect(startRes.status).toBe(200);

    const fillCalls: unknown[] = [];
    const mockClient: HostWorkerClient = {
      async createSession() {
        throw new Error('not used');
      },
      async fillSession(applicationId, profile) {
        fillCalls.push({ applicationId, profile });
        return {
          session: { status: 'ready' },
          fill: {
            filled: [
              { field: 'first_name', label: 'first name' },
              { field: 'email', label: 'email address' },
            ],
            missing: ['phone'],
            skipped: [{ label: 'resume', reason: 'unsupported_type_file' }],
          },
        };
      },
    };
    setHostWorkerClientForTests(mockClient);

    const fillRes = await request(app).post(`/api/apply/${startRes.body.application_id}/fill`);

    expect(fillRes.status).toBe(200);
    expect(fillRes.body.status).toBe('awaiting_input');
    expect(fillRes.body.fill.filled.map((item: any) => item.field)).toEqual(['first_name', 'email']);
    expect(fillRes.body.fill.missing).toEqual(['phone']);
    expect(fillCalls).toHaveLength(1);
    expect(fillCalls[0]).toMatchObject({
      applicationId: startRes.body.application_id,
      profile: {
        first_name: 'Bhawani',
        email: 'bhawani@example.com',
      },
    });

    const appRecord = db.prepare('SELECT status, current_step FROM applications WHERE id = ?').get(startRes.body.application_id) as any;
    expect(appRecord).toEqual({
      status: 'awaiting_input',
      current_step: 'form_fill_missing_fields',
    });

    const events = db.prepare('SELECT event_type, event_json as details_json FROM application_events WHERE application_id = ?').all(startRes.body.application_id) as any[];
    const eventTypes = events.map(e => e.event_type);
    expect(eventTypes).toContain('form_fill_missing_fields');
    const eventJson = JSON.stringify(events);
    expect(eventJson).toContain('first_name');
    expect(eventJson).toContain('first name');
    expect(eventJson).toContain('phone');
    expect(eventJson).not.toContain('+911234567890');
  });

  it('should accept missing input and transition to ready', async () => {
    const db = getDb();
    db.prepare('INSERT INTO users (id, telegram_user_id) VALUES (?, ?)').run('u2', 'test_tg_id_2');
    db.prepare('INSERT INTO user_profiles (user_id, profile_json) VALUES (?, ?)').run(
      'u2',
      JSON.stringify({
        first_name: 'Input',
        last_name: 'Test',
      }),
    );

    const startRes = await request(app)
      .post('/api/apply/start')
      .send({ telegram_user_id: 'test_tg_id_2', job_id: 'job2' });

    // Set status to awaiting_input manually
    db.prepare("UPDATE applications SET status = 'awaiting_input' WHERE id = ?").run(startRes.body.application_id);

    const provideRes = await request(app)
      .post(`/api/apply/${startRes.body.application_id}/provide-input`)
      .send({
        answers: {
          phone: '+1234567890',
          resume: '/path/to/resume.pdf'
        }
      });

    expect(provideRes.status).toBe(200);
    expect(provideRes.body.status).toBe('ready');

    const appRecord = db.prepare('SELECT status FROM applications WHERE id = ?').get(startRes.body.application_id) as any;
    expect(appRecord.status).toBe('ready');

    const profileRecord = db.prepare('SELECT profile_json FROM user_profiles WHERE user_id = ?').get('u2') as any;
    const updatedProfile = JSON.parse(profileRecord.profile_json);
    expect(updatedProfile.phone).toBe('+1234567890');
    expect(updatedProfile.resume).toBe('/path/to/resume.pdf');
  });

  it('should require user input when a profile is missing before fill', async () => {
    const startRes = await request(app)
      .post('/api/apply/start')
      .send({ telegram_user_id: 'test_tg_id', job_id: 'job1' });
    expect(startRes.status).toBe(200);

    const mockClient: HostWorkerClient = {
      async createSession() {
        throw new Error('not used');
      },
      async fillSession() {
        throw new Error('not used');
      },
    };
    setHostWorkerClientForTests(mockClient);

    const fillRes = await request(app).post(`/api/apply/${startRes.body.application_id}/fill`);

    expect(fillRes.status).toBe(409);
    expect(fillRes.body.status).toBe('needs_user_input');
    expect(fillRes.body.error).toBe('User profile is missing');

    const db = getDb();
    const appRecord = db.prepare('SELECT status, current_step FROM applications WHERE id = ?').get(startRes.body.application_id) as any;
    expect(appRecord).toEqual({
      status: 'needs_user_input',
      current_step: 'profile_missing',
    });
  });

  it('should record form fill failures from the host worker', async () => {
    const db = getDb();
    db.prepare('INSERT INTO user_profiles (user_id, profile_json) VALUES (?, ?)').run(
      'u1',
      JSON.stringify({ email: 'bhawani@example.com' }),
    );

    const startRes = await request(app)
      .post('/api/apply/start')
      .send({ telegram_user_id: 'test_tg_id', job_id: 'job1' });
    expect(startRes.status).toBe(200);

    const mockClient: HostWorkerClient = {
      async createSession() {
        throw new Error('not used');
      },
      async fillSession() {
        throw new Error('Session not found: app');
      },
    };
    setHostWorkerClientForTests(mockClient);

    const fillRes = await request(app).post(`/api/apply/${startRes.body.application_id}/fill`);

    expect(fillRes.status).toBe(502);
    expect(fillRes.body.status).toBe('failed');
    expect(fillRes.body.error).toBe('Session not found: app');

    const appRecord = db.prepare('SELECT status, current_step FROM applications WHERE id = ?').get(startRes.body.application_id) as any;
    expect(appRecord).toEqual({
      status: 'failed',
      current_step: 'form_fill_failed',
    });

    const event = db.prepare(`
      SELECT event_json FROM application_events
      WHERE application_id = ? AND event_type = 'form_fill_failed'
    `).get(startRes.body.application_id) as any;
    expect(event.event_json).toContain('Session not found');
  });

  it('should pass the latest readable resume path to the host worker during fill', async () => {
    const db = getDb();
    const resumePath = path.join(os.tmpdir(), `apply-engine-readable-resume-${Date.now()}.pdf`);
    fs.writeFileSync(resumePath, '%PDF-1.4\n% test resume\n');

    db.prepare('INSERT INTO user_profiles (user_id, profile_json) VALUES (?, ?)').run(
      'u1',
      JSON.stringify({ email: 'bhawani@example.com' }),
    );
    db.prepare(`
      INSERT INTO resumes (id, user_id, label, file_path, original_filename)
      VALUES (?, ?, ?, ?, ?)
    `).run('resume_readable', 'u1', 'Default Resume', resumePath, 'resume.pdf');

    const startRes = await request(app)
      .post('/api/apply/start')
      .send({ telegram_user_id: 'test_tg_id', job_id: 'job1' });
    expect(startRes.status).toBe(200);

    const fillCalls: unknown[] = [];
    const mockClient: HostWorkerClient = {
      async createSession() {
        throw new Error('not used');
      },
      async fillSession(applicationId, profile, passedResumePath) {
        fillCalls.push({ applicationId, profile, passedResumePath });
        return {
          session: { status: 'ready' },
          fill: {
            filled: [{ field: 'resume', label: 'resume' }],
            missing: [],
            skipped: [],
          },
        };
      },
    };
    setHostWorkerClientForTests(mockClient);

    const fillRes = await request(app).post(`/api/apply/${startRes.body.application_id}/fill`);

    expect(fillRes.status).toBe(200);
    expect(fillCalls).toHaveLength(1);
    expect(fillCalls[0]).toMatchObject({
      applicationId: startRes.body.application_id,
      passedResumePath: resumePath,
    });
  });

  it('should not pass an unreadable or missing resume path to the host worker', async () => {
    const db = getDb();
    const missingResumePath = path.join(os.tmpdir(), `missing-resume-${Date.now()}.pdf`);

    db.prepare('INSERT INTO user_profiles (user_id, profile_json) VALUES (?, ?)').run(
      'u1',
      JSON.stringify({ email: 'bhawani@example.com' }),
    );
    db.prepare(`
      INSERT INTO resumes (id, user_id, label, file_path, original_filename)
      VALUES (?, ?, ?, ?, ?)
    `).run('resume_missing', 'u1', 'Default Resume', missingResumePath, 'resume.pdf');

    const startRes = await request(app)
      .post('/api/apply/start')
      .send({ telegram_user_id: 'test_tg_id', job_id: 'job1' });
    expect(startRes.status).toBe(200);

    const fillCalls: unknown[] = [];
    const mockClient: HostWorkerClient = {
      async createSession() {
        throw new Error('not used');
      },
      async fillSession(applicationId, profile, passedResumePath) {
        fillCalls.push({ applicationId, profile, passedResumePath });
        return {
          session: { status: 'ready' },
          fill: {
            filled: [],
            missing: ['resume'],
            skipped: [],
          },
        };
      },
    };
    setHostWorkerClientForTests(mockClient);

    const fillRes = await request(app).post(`/api/apply/${startRes.body.application_id}/fill`);

    expect(fillRes.status).toBe(200);
    expect(fillCalls).toHaveLength(1);
    expect(fillCalls[0]).toMatchObject({
      applicationId: startRes.body.application_id,
      passedResumePath: undefined,
    });
    expect(fillRes.body.fill.missing).toEqual(['resume']);
  });

  it('should create a profile for a new telegram user', async () => {
    const res = await request(app)
      .put('/api/users/new_profile_user/profile')
      .send({
        first_name: '  Bhawani  ',
        email: 'bhawani@example.com',
        linkedin_url: 'https://linkedin.com/in/example',
        notice_period: 30,
      });

    expect(res.status).toBe(200);
    expect(res.body).toMatchObject({
      status: 'success',
      telegram_user_id: 'new_profile_user',
      profile: {
        first_name: 'Bhawani',
        email: 'bhawani@example.com',
        linkedin_url: 'https://linkedin.com/in/example',
        notice_period: '30',
      },
    });

    const db = getDb();
    const user = db.prepare('SELECT id FROM users WHERE telegram_user_id = ?').get('new_profile_user') as any;
    expect(user.id).toBe('user_new_profile_user');

    const profile = db.prepare('SELECT profile_json FROM user_profiles WHERE user_id = ?').get(user.id) as any;
    expect(JSON.parse(profile.profile_json)).toEqual(res.body.profile);
  });

  it('should update and fetch an existing profile', async () => {
    await request(app)
      .put('/api/users/test_tg_id/profile')
      .send({ first_name: 'Old', email: 'old@example.com' })
      .expect(200);

    await request(app)
      .put('/api/users/test_tg_id/profile')
      .send({ first_name: 'Bhawani', github_url: 'https://github.com/example' })
      .expect(200);

    const res = await request(app).get('/api/users/test_tg_id/profile');

    expect(res.status).toBe(200);
    expect(res.body).toEqual({
      telegram_user_id: 'test_tg_id',
      profile: {
        first_name: 'Bhawani',
        github_url: 'https://github.com/example',
      },
    });
  });

  it('should reject invalid profile payloads', async () => {
    const arrayRes = await request(app)
      .put('/api/users/test_tg_id/profile')
      .send([]);

    expect(arrayRes.status).toBe(400);
    expect(arrayRes.body.error).toBe('Profile data must be a JSON object');

    const unknownFieldRes = await request(app)
      .put('/api/users/test_tg_id/profile')
      .send({ password: 'secret' });

    expect(unknownFieldRes.status).toBe(400);
    expect(unknownFieldRes.body.error).toBe('Unsupported profile field: password');

    const invalidUrlRes = await request(app)
      .put('/api/users/test_tg_id/profile')
      .send({ linkedin_url: 'javascript:alert(1)' });

    expect(invalidUrlRes.status).toBe(400);
    expect(invalidUrlRes.body.error).toBe('Profile field linkedin_url must be an http or https URL');
  });

  it('should keep a saved profile available after application start', async () => {
    await request(app)
      .put('/api/users/test_tg_id/profile')
      .send({ first_name: 'Bhawani', email: 'bhawani@example.com' })
      .expect(200);

    const startRes = await request(app)
      .post('/api/apply/start')
      .send({ telegram_user_id: 'test_tg_id', job_id: 'job1' });

    expect(startRes.status).toBe(200);

    const profileRes = await request(app).get('/api/users/test_tg_id/profile');
    expect(profileRes.status).toBe(200);
    expect(profileRes.body.profile).toEqual({
      first_name: 'Bhawani',
      email: 'bhawani@example.com',
    });
  });
});
