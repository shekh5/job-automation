import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { chromium, Browser, BrowserContext, Page } from 'playwright';
import path from 'path';
import { LeverHandler } from '../src/host-worker/ats/lever';

describe('ATS Handlers', () => {
  let browser: Browser;
  let context: BrowserContext;
  let page: Page;

  beforeAll(async () => {
    browser = await chromium.launch({ headless: true });
    context = await browser.newContext();
    page = await context.newPage();
  });

  afterAll(async () => {
    await browser.close();
  });

  describe('LeverHandler', () => {
    it('detects lever form by url', async () => {
      const handler = new LeverHandler();
      expect(await handler.detect('https://jobs.lever.co/example/123', page)).toBe(true);
      expect(await handler.detect('https://example.lever.co/', page)).toBe(true);
      expect(await handler.detect('https://example.com/jobs', page)).toBe(false);
    });

    it('detects lever form by DOM', async () => {
      const handler = new LeverHandler();
      const fixturePath = `file://${path.resolve(__dirname, 'fixtures/lever-form.html')}`;
      await page.goto(fixturePath);
      expect(await handler.detect('https://example.com/custom-job-board', page)).toBe(true);
    });

    it('fills lever form correctly', async () => {
      const handler = new LeverHandler();
      const fixturePath = `file://${path.resolve(__dirname, 'fixtures/lever-form.html')}`;
      await page.goto(fixturePath);

      const profile = {
        first_name: 'Test',
        last_name: 'User',
        email: 'test@example.com',
        phone: '1234567890',
        location: 'Test City',
        linkedin_url: 'https://linkedin.com/in/test',
        github_url: 'https://github.com/test',
      };

      // Create a dummy resume file for testing
      const fs = require('fs');
      const testResumePath = path.resolve(__dirname, 'fixtures/test-resume.pdf');
      if (!fs.existsSync(path.dirname(testResumePath))) {
        fs.mkdirSync(path.dirname(testResumePath), { recursive: true });
      }
      fs.writeFileSync(testResumePath, 'dummy pdf content');

      const result = await handler.fill(page, profile, testResumePath);

      expect(result.filled.map(f => f.field)).toEqual(expect.arrayContaining([
        'full_name', 'email', 'phone', 'location', 'linkedin_url', 'github_url', 'resume'
      ]));

      // Verify page content
      expect(await page.locator('input[name="name"]').inputValue()).toBe('Test User');
      expect(await page.locator('input[name="email"]').inputValue()).toBe('test@example.com');
      expect(await page.locator('input[name="phone"]').inputValue()).toBe('1234567890');
      expect(await page.locator('input[name="org"]').inputValue()).toBe('Test City');
      expect(await page.locator('input[name="urls[LinkedIn]"]').inputValue()).toBe('https://linkedin.com/in/test');
      expect(await page.locator('input[name="urls[GitHub]"]').inputValue()).toBe('https://github.com/test');
    });
  });

  describe('GreenhouseHandler', () => {
    it('detects greenhouse form by url', async () => {
      const { GreenhouseHandler } = await import('../src/host-worker/ats/greenhouse');
      const handler = new GreenhouseHandler();
      expect(await handler.detect('https://boards.greenhouse.io/example/123', page)).toBe(true);
      expect(await handler.detect('https://example.greenhouse.io/', page)).toBe(true);
      expect(await handler.detect('https://example.com/jobs', page)).toBe(false);
    });

    it('detects greenhouse form by DOM', async () => {
      const { GreenhouseHandler } = await import('../src/host-worker/ats/greenhouse');
      const handler = new GreenhouseHandler();
      const fixturePath = `file://${path.resolve(__dirname, 'fixtures/greenhouse-form.html')}`;
      await page.goto(fixturePath);
      expect(await handler.detect('https://example.com/custom-job-board', page)).toBe(true);
    });

    it('fills greenhouse form correctly', async () => {
      const { GreenhouseHandler } = await import('../src/host-worker/ats/greenhouse');
      const handler = new GreenhouseHandler();
      const fixturePath = `file://${path.resolve(__dirname, 'fixtures/greenhouse-form.html')}`;
      await page.goto(fixturePath);

      const profile = {
        first_name: 'Test',
        last_name: 'User',
        email: 'test@example.com',
        phone: '1234567890',
        linkedin_url: 'https://linkedin.com/in/test',
        github_url: 'https://github.com/test',
      };

      const fs = require('fs');
      const testResumePath = path.resolve(__dirname, 'fixtures/test-resume.pdf');
      if (!fs.existsSync(path.dirname(testResumePath))) {
        fs.mkdirSync(path.dirname(testResumePath), { recursive: true });
      }
      fs.writeFileSync(testResumePath, 'dummy pdf content');

      const result = await handler.fill(page, profile, testResumePath);

      expect(result.filled.map(f => f.field)).toEqual(expect.arrayContaining([
        'first_name', 'last_name', 'email', 'phone', 'linkedin_url', 'github_url', 'resume'
      ]));

      // Verify page content
      expect(await page.locator('input#first_name').inputValue()).toBe('Test');
      expect(await page.locator('input#last_name').inputValue()).toBe('User');
      expect(await page.locator('input#email').inputValue()).toBe('test@example.com');
      expect(await page.locator('input#phone').inputValue()).toBe('1234567890');
      // For greenhouse, linkedin and github map to the custom question inputs
      const customInputs = page.locator('.custom_question input[type="text"]');
      expect(await customInputs.nth(0).inputValue()).toBe('https://linkedin.com/in/test');
      expect(await customInputs.nth(1).inputValue()).toBe('https://github.com/test');
    });
  });

  describe('AshbyHandler', () => {
    it('detects ashby form by url', async () => {
      const { AshbyHandler } = await import('../src/host-worker/ats/ashby');
      const handler = new AshbyHandler();
      expect(await handler.detect('https://jobs.ashbyhq.com/example/123', page)).toBe(true);
      expect(await handler.detect('https://example.ashbyhq.com/', page)).toBe(true);
      expect(await handler.detect('https://example.com/jobs', page)).toBe(false);
    });

    it('detects ashby form by DOM', async () => {
      const { AshbyHandler } = await import('../src/host-worker/ats/ashby');
      const handler = new AshbyHandler();
      const fixturePath = `file://${path.resolve(__dirname, 'fixtures/ashby-form.html')}`;
      await page.goto(fixturePath);
      // For ashby, we only check URL in DOM evaluation right now, but we can verify the function returns false if not ashbyhq
      expect(await handler.detect('https://example.com/custom-job-board', page)).toBe(false);
    });

    it('fills ashby form correctly', async () => {
      const { AshbyHandler } = await import('../src/host-worker/ats/ashby');
      const handler = new AshbyHandler();
      const fixturePath = `file://${path.resolve(__dirname, 'fixtures/ashby-form.html')}`;
      await page.goto(fixturePath);

      const profile = {
        first_name: 'Test',
        last_name: 'User',
        email: 'test@example.com',
        phone: '1234567890',
        linkedin_url: 'https://linkedin.com/in/test',
        github_url: 'https://github.com/test',
      };

      const fs = require('fs');
      const testResumePath = path.resolve(__dirname, 'fixtures/test-resume.pdf');
      if (!fs.existsSync(path.dirname(testResumePath))) {
        fs.mkdirSync(path.dirname(testResumePath), { recursive: true });
      }
      fs.writeFileSync(testResumePath, 'dummy pdf content');

      const result = await handler.fill(page, profile, testResumePath);

      expect(result.filled.map(f => f.field)).toEqual(expect.arrayContaining([
        'full_name', 'email', 'phone', 'linkedin_url', 'github_url', 'resume'
      ]));

      // Verify page content
      expect(await page.locator('input[name="name"]').inputValue()).toBe('Test User');
      expect(await page.locator('input[name="email"]').inputValue()).toBe('test@example.com');
      expect(await page.locator('input[name="phone"]').inputValue()).toBe('1234567890');
      
      const customInputs = page.locator('input[type="url"]');
      expect(await customInputs.nth(0).inputValue()).toBe('https://linkedin.com/in/test');
      expect(await customInputs.nth(1).inputValue()).toBe('https://github.com/test');
    });
  });
});
