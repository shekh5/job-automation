import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { BrowserWorker } from '../src/browser/browserWorker';
import os from 'os';
import path from 'path';

describe('BrowserWorker', () => {
  let worker: BrowserWorker;

  beforeAll(async () => {
    process.env.BROWSER_STORAGE_DIR = path.join(os.tmpdir(), 'telegram-apply-engine-browser-tests');
    worker = new BrowserWorker('test-session-123');
    await worker.start(true); // Headless for testing
  });

  afterAll(async () => {
    await worker.close();
  });

  it('should navigate and take a screenshot', async () => {
    // Navigate to a fast, light test page
    await worker.navigate('data:text/html,<html><body><h1>Test Form</h1><form><input type="text" id="test-input" /></form></body></html>');
    
    // Check if page object exists
    expect(worker.page).toBeDefined();

    // Verify title or content
    const heading = await worker.page!.$eval('h1', el => el.textContent);
    expect(heading).toBe('Test Form');

    // Take screenshot
    const base64Image = await worker.captureScreenshot();
    expect(typeof base64Image).toBe('string');
    expect(base64Image.length).toBeGreaterThan(100);
  });
});
