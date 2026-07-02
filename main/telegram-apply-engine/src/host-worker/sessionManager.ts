import { chromium, BrowserContext, Page } from 'playwright';
import path from 'path';
import { fillCommonFields, type ApplicantProfile, type FillResult } from './formFiller';
import { detectAts } from './ats/detector';

export type SessionStatus = 'created' | 'opening' | 'ready' | 'failed' | 'closed';

export interface CreateSessionInput {
  application_id: string;
  url?: string;
  profile_id?: string;
  headless?: boolean;
}

export interface WorkerSessionSnapshot {
  application_id: string;
  profile_id: string;
  status: SessionStatus;
  current_url: string | null;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface FillSessionResult {
  session: WorkerSessionSnapshot;
  fill: FillResult;
}

interface WorkerSession {
  applicationId: string;
  profileId: string;
  status: SessionStatus;
  currentUrl: string | null;
  error: string | null;
  createdAt: string;
  updatedAt: string;
  context: BrowserContext | null;
  page: Page | null;
}

function nowIso() {
  return new Date().toISOString();
}

function normalizeProfileId(profileId: string | undefined) {
  return (profileId || 'default').replace(/[^a-zA-Z0-9_-]/g, '_');
}

export class HostWorkerSessionManager {
  private sessions = new Map<string, WorkerSession>();
  private profileRoot: string;
  private defaultHeadless: boolean;

  constructor(options?: { profileRoot?: string; defaultHeadless?: boolean }) {
    this.profileRoot = options?.profileRoot || process.env.BROWSER_PROFILE_DIR || path.join(__dirname, '../../data/browser-profiles');
    this.defaultHeadless = options?.defaultHeadless ?? process.env.HOST_WORKER_HEADLESS === 'true';
  }

  listSessions() {
    return Array.from(this.sessions.values()).map(session => this.snapshot(session));
  }

  getSession(applicationId: string) {
    const session = this.sessions.get(applicationId);
    return session ? this.snapshot(session) : null;
  }

  async createSession(input: CreateSessionInput) {
    const existing = this.sessions.get(input.application_id);
    if (existing && existing.status !== 'closed') {
      if (input.url) {
        await this.navigate(input.application_id, input.url);
      }
      return this.snapshot(existing);
    }

    const profileId = normalizeProfileId(input.profile_id);
    const timestamp = nowIso();
    const session: WorkerSession = {
      applicationId: input.application_id,
      profileId,
      status: 'created',
      currentUrl: null,
      error: null,
      createdAt: timestamp,
      updatedAt: timestamp,
      context: null,
      page: null,
    };

    this.sessions.set(input.application_id, session);
    await this.openBrowser(session, input.headless);

    if (input.url) {
      await this.navigate(input.application_id, input.url);
    }

    return this.snapshot(session);
  }

  async navigate(applicationId: string, url: string) {
    const session = this.requireSession(applicationId);
    if (!session.page) {
      throw new Error('Browser page is not available');
    }

    session.status = 'opening';
    session.updatedAt = nowIso();

    try {
      await session.page.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 });
      await this.syncActivePage(session);
      session.currentUrl = session.page.url();
      session.status = 'ready';
      session.error = null;
    } catch (error) {
      session.status = 'failed';
      session.error = error instanceof Error ? error.message : String(error);
    } finally {
      session.updatedAt = nowIso();
    }

    return this.snapshot(session);
  }

  async fillSession(applicationId: string, profile: ApplicantProfile, resumePath?: string): Promise<FillSessionResult> {
    const session = this.requireSession(applicationId);
    if (!session.page) {
      throw new Error('Browser page is not available');
    }

    await this.syncActivePage(session);
    const currentUrl = session.page.url();
    const handler = await detectAts(currentUrl, session.page);
    console.log('DETECTED HANDLER:', handler?.name);

    let fill;
    if (handler) {
      fill = await handler.fill(session.page, profile, resumePath);
    } else {
      fill = await fillCommonFields(session.page, profile, resumePath);
    }

    session.currentUrl = session.page.url();
    session.updatedAt = nowIso();
    return { session: this.snapshot(session), fill };
  }

  async submitSession(applicationId: string) {
    const session = this.requireSession(applicationId);
    if (!session.page) {
      throw new Error('Browser page is not available');
    }

    try {
      await this.syncActivePage(session);
      await this.clickSubmitButton(session.page);
      
      session.currentUrl = session.page.url();
      session.updatedAt = nowIso();
      return { session: this.snapshot(session), submitted: true };
    } catch (error) {
      session.error = error instanceof Error ? error.message : String(error);
      session.updatedAt = nowIso();
      throw error;
    }
  }

  async verifySession(applicationId: string, code: string) {
    const session = this.requireSession(applicationId);
    if (!session.page) {
      throw new Error('Browser page is not available');
    }

    try {
      await this.syncActivePage(session);
      await session.page.waitForLoadState('domcontentloaded', { timeout: 10000 }).catch(() => {});

      const characterInputs = session.page.locator('input[maxlength="1"], input[aria-label*="digit" i], input[aria-label*="code" i]');
      const characterInputCount = await characterInputs.count();

      if (characterInputCount >= code.length) {
        for (let index = 0; index < code.length; index += 1) {
          await characterInputs.nth(index).fill(code[index]);
        }
      } else {
        const codeInput = session.page.locator([
          'input[name*="security" i]',
          'input[id*="security" i]',
          'input[name*="verification" i]',
          'input[id*="verification" i]',
          'input[name*="code" i]',
          'input[id*="code" i]',
          'input[autocomplete="one-time-code"]',
          'input[type="text"]',
        ].join(', ')).last();

        if ((await codeInput.count()) === 0) {
          throw new Error('Could not find a security code field on the page');
        }

        await codeInput.fill(code);
      }

      await session.page.waitForTimeout(500);
      await this.clickSubmitButton(session.page);

      session.currentUrl = session.page.url();
      session.updatedAt = nowIso();
      return { session: this.snapshot(session), verified: true };
    } catch (error) {
      session.error = error instanceof Error ? error.message : String(error);
      session.updatedAt = nowIso();
      throw error;
    }
  }

  async closeSession(applicationId: string) {
    const session = this.requireSession(applicationId);

    if (session.context) {
      await session.context.close();
    }

    session.context = null;
    session.page = null;
    session.status = 'closed';
    session.updatedAt = nowIso();
    return this.snapshot(session);
  }

  async closeAll() {
    await Promise.all(Array.from(this.sessions.keys()).map(async id => {
      const session = this.sessions.get(id);
      if (session?.context) {
        await session.context.close();
      }
      if (session) {
        session.context = null;
        session.page = null;
        session.status = 'closed';
        session.updatedAt = nowIso();
      }
    }));
  }

  async inspectSession(applicationId: string) {
    const session = this.requireSession(applicationId);
    if (!session.page) {
      throw new Error('Browser page is not available');
    }

    await this.syncActivePage(session);
    const page = session.page;
    const inspection = await page.evaluate(`(() => {
      const summarizeInput = (element, index) => {
        const input = element;
        const id = input.getAttribute('id') || '';
        const label = id ? document.querySelector('label[for="' + CSS.escape(id) + '"]')?.textContent || '' : '';
        const rect = input.getBoundingClientRect();
        return {
          index,
          tag: input.tagName.toLowerCase(),
          type: input.tagName.toLowerCase() === 'input' ? input.type : 'textarea',
          id,
          name: input.getAttribute('name') || '',
          placeholder: input.getAttribute('placeholder') || '',
          ariaLabel: input.getAttribute('aria-label') || '',
          label: label.trim(),
          value: input.value,
          disabled: !!input.disabled,
          readOnly: !!input.readOnly,
          visible: !!(input.offsetWidth || input.offsetHeight || input.getClientRects().length),
          box: { x: rect.x, y: rect.y, width: rect.width, height: rect.height }
        };
      };

      const summarizeButton = (element, index) => {
        const button = element;
        const rect = button.getBoundingClientRect();
        return {
          index,
          tag: button.tagName.toLowerCase(),
          type: button.getAttribute('type') || '',
          text: (button.textContent || button.getAttribute('value') || '').trim(),
          disabled: !!button.disabled,
          ariaDisabled: button.getAttribute('aria-disabled') || '',
          visible: !!(button.offsetWidth || button.offsetHeight || button.getClientRects().length),
          box: { x: rect.x, y: rect.y, width: rect.width, height: rect.height }
        };
      };

      return {
        title: document.title,
        url: window.location.href,
        bodyText: (document.body && document.body.innerText ? document.body.innerText : '').slice(0, 3000),
        inputs: Array.from(document.querySelectorAll('input, textarea')).map(summarizeInput),
        buttons: Array.from(document.querySelectorAll('button, input[type="submit"], input[type="button"]')).map(summarizeButton),
      };
    })()`);

    return { session: this.snapshot(session), inspection };
  }

  async screenshotSession(applicationId: string) {
    const session = this.requireSession(applicationId);
    if (!session.page) {
      throw new Error('Browser page is not available');
    }

    await this.syncActivePage(session);
    return await session.page.screenshot({ type: 'png', fullPage: true });
  }

  private async openBrowser(session: WorkerSession, headlessOverride?: boolean) {
    const profileDir = path.join(this.profileRoot, session.profileId);
    const headless = headlessOverride ?? this.defaultHeadless;
    const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH;
    const channel = executablePath ? undefined : process.env.CHROME_CHANNEL || (headless ? undefined : 'chrome');
    const extraArgs = [
      '--disable-dev-shm-usage',
      '--disable-background-timer-throttling',
      '--disable-renderer-backgrounding',
      '--disable-backgrounding-occluded-windows',
      '--no-first-run',
      '--no-default-browser-check',
    ];

    console.log('Launching browser', {
      profileDir,
      headless,
      executablePath: executablePath || null,
      channel: channel || null,
      extraArgs,
    });

    try {
      session.context = await chromium.launchPersistentContext(profileDir, {
        ...(channel ? { channel } : {}),
        ...(executablePath ? { executablePath } : {}),
        headless,
        args: extraArgs,
        viewport: { width: 1280, height: 900 },
      });
      session.page = session.context.pages()[0] || await session.context.newPage();
      session.currentUrl = session.page.url();
      session.status = 'ready';
      session.error = null;
    } catch (error) {
      session.status = 'failed';
      session.error = error instanceof Error ? error.message : String(error);
      throw error;
    } finally {
      session.updatedAt = nowIso();
    }
  }

  private requireSession(applicationId: string) {
    const session = this.sessions.get(applicationId);
    if (!session) {
      throw new Error(`Session not found: ${applicationId}`);
    }
    return session;
  }

  private async clickSubmitButton(page: Page) {
    const selectors = 'button[type="submit"], input[type="submit"], button:has-text("Submit Application"), button:has-text("Submit application"), button:has-text("Submit"), button:has-text("Verify"), button:has-text("Continue")';
    const frames = page.frames();

    let sawAny = false;
    for (const frame of frames) {
      const submitButtons = frame.locator(selectors);
      const count = await submitButtons.count();
      if (count === 0) continue;
      sawAny = true;

      for (let index = count - 1; index >= 0; index -= 1) {
        const button = submitButtons.nth(index);
        if (!(await button.isVisible().catch(() => false))) continue;
        if (await button.isDisabled().catch(() => false)) continue;
        const ariaDisabled = await button.getAttribute('aria-disabled').catch(() => null);
        if (ariaDisabled === 'true') continue;
        await button.click();
        return;
      }
    }

    if (!sawAny) {
      throw new Error('Could not find a submit button on the page');
    }

    throw new Error('Could not find an enabled submit button on the page');
  }

  async clickElement(applicationId: string, selector: string) {
    const session = this.requireSession(applicationId);
    if (!session.page) throw new Error('Browser page is not available');
    await this.syncActivePage(session);
    const locator = session.page.locator(selector).first();
    try {
      await locator.click({ timeout: 5000 });
    } catch (error) {
      console.log(`Click intercepted/timed out for ${selector}, forcing click...`);
      try {
        await locator.click({ force: true, timeout: 2000 });
      } catch (forceError) {
        console.log(`Force click failed for ${selector}, trying parent...`);
        await locator.locator('..').click({ force: true, timeout: 2000 });
      }
    }
    return { session: this.snapshot(session) };
  }

  async typeElement(applicationId: string, selector: string, text: string) {
    const session = this.requireSession(applicationId);
    if (!session.page) throw new Error('Browser page is not available');
    await this.syncActivePage(session);
    const locator = session.page.locator(selector).first();
    try {
      await locator.fill(text, { timeout: 5000 });
    } catch (error) {
      console.log(`Fill intercepted/timed out for ${selector}, forcing fill...`);
      await locator.fill(text, { force: true, timeout: 2000 });
    }
    return { session: this.snapshot(session) };
  }

  async clickCoordinate(applicationId: string, x: number, y: number) {
    const session = this.requireSession(applicationId);
    if (!session.page) throw new Error('Browser page is not available');
    await this.syncActivePage(session);
    await session.page.mouse.click(x, y);
    return { session: this.snapshot(session) };
  }

  async typeCoordinate(applicationId: string, x: number, y: number, text: string) {
    const session = this.requireSession(applicationId);
    if (!session.page) throw new Error('Browser page is not available');
    await this.syncActivePage(session);
    await session.page.mouse.click(x, y);
    await session.page.keyboard.type(text);
    return { session: this.snapshot(session) };
  }

  async evaluateScript(applicationId: string, script: string) {
    const session = this.requireSession(applicationId);
    if (!session.page) throw new Error('Browser page is not available');
    await this.syncActivePage(session);
    const result = await session.page.evaluate(script);
    return { session: this.snapshot(session), result };
  }

  private async syncActivePage(session: WorkerSession) {
    if (!session.context) return;
    const pages = session.context.pages().filter(page => !page.isClosed());
    if (pages.length === 0) {
      session.page = null;
      return;
    }

    // Workday and other ATSs sometimes spawn the application form in a new tab
    // or popup. Prefer the newest live page so fill/submit runs on the form.
    const latestPage = pages[pages.length - 1];
    session.page = latestPage;
    session.currentUrl = latestPage.url();
  }

  private snapshot(session: WorkerSession): WorkerSessionSnapshot {
    return {
      application_id: session.applicationId,
      profile_id: session.profileId,
      status: session.status,
      current_url: session.currentUrl,
      error: session.error,
      created_at: session.createdAt,
      updated_at: session.updatedAt,
    };
  }
}
