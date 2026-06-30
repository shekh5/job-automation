import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import request from 'supertest';
import os from 'os';
import path from 'path';
import fs from 'fs';
import { createHostWorkerApp } from '../src/host-worker/server';
import { HostWorkerSessionManager } from '../src/host-worker/sessionManager';

describe('Host Chrome Worker API', () => {
  let manager: HostWorkerSessionManager;
  let app: ReturnType<typeof createHostWorkerApp>['app'];

  beforeEach(() => {
    manager = new HostWorkerSessionManager({
      profileRoot: path.join(os.tmpdir(), `telegram-apply-engine-host-worker-tests-${Date.now()}`),
      defaultHeadless: true,
    });
    app = createHostWorkerApp(manager).app;
  });

  afterEach(async () => {
    await manager.closeAll();
  });

  it('should report health', async () => {
    const res = await request(app).get('/health');

    expect(res.status).toBe(200);
    expect(res.body.ok).toBe(true);
    expect(res.body.service).toBe('host-chrome-worker');
  });

  it('should create, navigate, report, and close a browser session', async () => {
    const createRes = await request(app)
      .post('/sessions')
      .send({
        application_id: 'app_test_1',
        url: 'data:text/html,<html><body><h1>Host Worker</h1></body></html>',
        headless: true,
      });

    expect(createRes.status).toBe(201);
    expect(createRes.body.session.application_id).toBe('app_test_1');
    expect(createRes.body.session.status).toBe('ready');
    expect(createRes.body.session.current_url).toContain('data:text/html');

    const statusRes = await request(app).get('/sessions/app_test_1/status');
    expect(statusRes.status).toBe(200);
    expect(statusRes.body.session.status).toBe('ready');

    const navigateRes = await request(app)
      .post('/sessions/app_test_1/navigate')
      .send({ url: 'data:text/html,<html><body><h1>Next</h1></body></html>' });
    expect(navigateRes.status).toBe(200);
    expect(navigateRes.body.session.current_url).toContain('data:text/html');

    const closeRes = await request(app).post('/sessions/app_test_1/close');
    expect(closeRes.status).toBe(200);
    expect(closeRes.body.session.status).toBe('closed');
  }, 15000);

  it('should fill common profile fields without submitting the form', async () => {
    const html = encodeURIComponent(`
      <html>
        <body>
          <form id="apply-form">
            <label for="firstName">First Name</label>
            <input id="firstName" name="first_name" />
            <label for="lastName">Last Name</label>
            <input id="lastName" name="last_name" />
            <label for="email">Email Address</label>
            <input id="email" type="email" />
            <label for="phone">Phone</label>
            <input id="phone" type="tel" />
            <label for="linkedin">LinkedIn</label>
            <input id="linkedin" type="url" />
            <label for="github">GitHub</label>
            <input id="github" type="url" />
            <label for="portfolio">Portfolio Website</label>
            <input id="portfolio" type="url" />
            <label for="location">Location</label>
            <textarea id="location"></textarea>
            <button id="submit" type="submit">Submit</button>
          </form>
          <script>
            window.submitCount = 0;
            document.getElementById('apply-form').addEventListener('submit', (event) => {
              event.preventDefault();
              window.submitCount += 1;
            });
          </script>
        </body>
      </html>
    `);

    await request(app)
      .post('/sessions')
      .send({
        application_id: 'app_fill_test',
        url: `data:text/html,${html}`,
        headless: true,
      })
      .expect(201);

    const fillRes = await request(app)
      .post('/sessions/app_fill_test/fill')
      .send({
        profile: {
          first_name: 'Bhawani',
          last_name: 'Singh',
          email: 'bhawani@example.com',
          phone: '+911234567890',
          location: 'Bengaluru',
          linkedin_url: 'https://linkedin.com/in/example',
          github_url: 'https://github.com/example',
          portfolio_url: 'https://example.dev',
        },
      });

    expect(fillRes.status).toBe(200);
    expect(fillRes.body.fill.filled.map((item: any) => item.field).sort()).toEqual([
      'email',
      'first_name',
      'github_url',
      'last_name',
      'linkedin_url',
      'location',
      'phone',
      'portfolio_url',
    ]);
    expect(fillRes.body.fill.missing).toEqual([]);

    const page = (manager as any).sessions.get('app_fill_test').page;
    const values = await page.evaluate(() => ({
      firstName: (document.querySelector('#firstName') as HTMLInputElement).value,
      lastName: (document.querySelector('#lastName') as HTMLInputElement).value,
      email: (document.querySelector('#email') as HTMLInputElement).value,
      phone: (document.querySelector('#phone') as HTMLInputElement).value,
      linkedin: (document.querySelector('#linkedin') as HTMLInputElement).value,
      github: (document.querySelector('#github') as HTMLInputElement).value,
      portfolio: (document.querySelector('#portfolio') as HTMLInputElement).value,
      location: (document.querySelector('#location') as HTMLTextAreaElement).value,
      submitCount: (window as any).submitCount,
    }));

    expect(values).toEqual({
      firstName: 'Bhawani',
      lastName: 'Singh',
      email: 'bhawani@example.com',
      phone: '+911234567890',
      linkedin: 'https://linkedin.com/in/example',
      github: 'https://github.com/example',
      portfolio: 'https://example.dev',
      location: 'Bengaluru',
      submitCount: 0,
    });
  }, 15000);

  it('should upload a resume file without submitting the form', async () => {
    const resumePath = path.join(os.tmpdir(), `resume-${Date.now()}.pdf`);
    fs.writeFileSync(resumePath, '%PDF-1.4\n% test resume\n');

    const html = encodeURIComponent(`
      <html>
        <body>
          <form id="apply-form">
            <label for="email">Email</label>
            <input id="email" type="email" />
            <label for="resume">Resume</label>
            <input id="resume" name="resume" type="file" />
            <button id="submit" type="submit">Submit</button>
          </form>
          <script>
            window.submitCount = 0;
            document.getElementById('apply-form').addEventListener('submit', (event) => {
              event.preventDefault();
              window.submitCount += 1;
            });
          </script>
        </body>
      </html>
    `);

    await request(app)
      .post('/sessions')
      .send({
        application_id: 'app_resume_upload_test',
        url: `data:text/html,${html}`,
        headless: true,
      })
      .expect(201);

    const fillRes = await request(app)
      .post('/sessions/app_resume_upload_test/fill')
      .send({
        profile: { email: 'bhawani@example.com' },
        resume_path: resumePath,
      });

    expect(fillRes.status).toBe(200);
    expect(fillRes.body.fill.filled.map((item: any) => item.field).sort()).toEqual(['email', 'resume']);
    expect(fillRes.body.fill.missing).toEqual([]);

    const page = (manager as any).sessions.get('app_resume_upload_test').page;
    const values = await page.evaluate(() => {
      const resume = document.querySelector('#resume') as HTMLInputElement;
      return {
        email: (document.querySelector('#email') as HTMLInputElement).value,
        resumeFileName: resume.files?.[0]?.name,
        submitCount: (window as any).submitCount,
      };
    });

    expect(values).toEqual({
      email: 'bhawani@example.com',
      resumeFileName: path.basename(resumePath),
      submitCount: 0,
    });
  }, 15000);

  it('should report a missing resume when the form has a file input but no resume path is provided', async () => {
    const html = encodeURIComponent(`
      <html><body><form><label for="resume">Resume</label><input id="resume" type="file" /></form></body></html>
    `);

    await request(app)
      .post('/sessions')
      .send({
        application_id: 'app_resume_missing_test',
        url: `data:text/html,${html}`,
        headless: true,
      })
      .expect(201);

    const fillRes = await request(app)
      .post('/sessions/app_resume_missing_test/fill')
      .send({ profile: {} });

    expect(fillRes.status).toBe(200);
    expect(fillRes.body.fill.missing).toEqual(['resume']);
    expect(fillRes.body.fill.filled).toEqual([]);
  }, 15000);

  it('should skip ambiguous upload fields instead of guessing', async () => {
    const resumePath = path.join(os.tmpdir(), `resume-ambiguous-${Date.now()}.pdf`);
    fs.writeFileSync(resumePath, '%PDF-1.4\n% test resume\n');

    const html = encodeURIComponent(`
      <html>
        <body>
          <form>
            <label for="cover">Cover Letter</label>
            <input id="cover" name="cover_letter" type="file" />
            <label for="portfolio">Portfolio Attachment</label>
            <input id="portfolio" name="portfolio_attachment" type="file" />
          </form>
        </body>
      </html>
    `);

    await request(app)
      .post('/sessions')
      .send({
        application_id: 'app_resume_ambiguous_test',
        url: `data:text/html,${html}`,
        headless: true,
      })
      .expect(201);

    const fillRes = await request(app)
      .post('/sessions/app_resume_ambiguous_test/fill')
      .send({
        profile: {},
        resume_path: resumePath,
      });

    expect(fillRes.status).toBe(200);
    expect(fillRes.body.fill.filled).toEqual([]);
    expect(fillRes.body.fill.skipped).toContainEqual({
      label: 'resume upload',
      reason: 'ambiguous_file_input',
    });
  }, 15000);

  it('should reject invalid session requests', async () => {
    const res = await request(app).post('/sessions').send({});

    expect(res.status).toBe(400);
    expect(res.body.error).toBe('Missing application_id');
  });

  it('should handle missing fields and allow retrying after input is provided', async () => {
    // Create an HTML fixture that requires phone and email
    const formHtml = `
      <html><body>
        <form>
          <label>Email <input type="email" name="email"></label>
          <label>Phone <input type="tel" name="phone"></label>
        </form>
      </body></html>
    `;
    const formUrl = `data:text/html,${encodeURIComponent(formHtml)}`;

    // Create a session
    await request(app)
      .post('/sessions')
      .send({
        application_id: 'app_test_retry',
        url: formUrl,
        headless: true,
      });

    // Profile without phone
    const profileWithoutPhone = {
      email: 'test@example.com'
    };

    const firstFill = await request(app)
      .post('/sessions/app_test_retry/fill')
      .send({ profile: profileWithoutPhone });

    expect(firstFill.status).toBe(200);
    const fillResult1 = firstFill.body.fill;
    
    // It should have filled email but missed phone
    expect(fillResult1.filled.map((f: any) => f.field)).toContain('email');
    expect(fillResult1.missing).toContain('phone');

    // Now user provides phone via the bot. The backend triggers fill again with updated profile
    const profileWithPhone = {
      email: 'test@example.com',
      phone: '1234567890'
    };

    const secondFill = await request(app)
      .post('/sessions/app_test_retry/fill')
      .send({ profile: profileWithPhone });

    expect(secondFill.status).toBe(200);
    const fillResult2 = secondFill.body.fill;

    // Email should be skipped (already filled), phone should be filled
    expect(fillResult2.filled.map((f: any) => f.field)).toContain('phone');
    expect(fillResult2.skipped.map((f: any) => f.reason)).toContain('already_filled');
    expect(fillResult2.missing).toEqual([]);
  }, 10000);
});
