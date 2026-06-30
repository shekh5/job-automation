import type { Page } from 'playwright';
import type { AtsHandler } from './types';
import type { ApplicantProfile, FillResult, FillField } from '../formFiller';

export class AshbyHandler implements AtsHandler {
  name = 'ashby';

  async detect(url: string, page: Page): Promise<boolean> {
    try {
      const parsedUrl = new URL(url);
      if (parsedUrl.hostname === 'jobs.ashbyhq.com' || parsedUrl.hostname.endsWith('.ashbyhq.com')) {
        return true;
      }
      
      const isAshby = await page.evaluate(() => {
        return window.location.href.includes('ashbyhq.com');
      });
      return isAshby;
    } catch {
      return false;
    }
  }

  async fill(page: Page, profile: ApplicantProfile, resumePath?: string): Promise<FillResult> {
    const result: FillResult = {
      filled: [],
      missing: [],
      skipped: [],
    };

    const attemptFill = async (field: FillField, selector: string, value: string | undefined) => {
      if (!value) {
        result.missing.push(field);
        return;
      }
      try {
        const count = await page.locator(selector).count();
        if (count > 0) {
          const locator = page.locator(selector).first();
          const disabled = await locator.isDisabled();
          if (disabled) {
            result.skipped.push({ label: field, reason: 'disabled_or_readonly' });
            return;
          }
          
          const currentValue = await locator.inputValue();
          if (currentValue) {
            result.skipped.push({ label: field, reason: 'already_filled' });
            return;
          }

          await locator.fill(value);
          result.filled.push({ field, label: field });
        } else {
          result.missing.push(field);
        }
      } catch (error) {
        result.skipped.push({ label: field, reason: 'error_filling' });
      }
    };

    // Ashby often uses specific IDs or names
    if (profile.full_name) {
      await attemptFill('full_name', 'input[name="name"]', profile.full_name);
    } else if (profile.first_name || profile.last_name) {
      await attemptFill('full_name', 'input[name="name"]', `${profile.first_name || ''} ${profile.last_name || ''}`.trim());
    } else {
      result.missing.push('full_name');
    }

    await attemptFill('email', 'input[name="email"]', profile.email);
    await attemptFill('phone', 'input[name="phone"]', profile.phone);

    const fillCustomLabel = async (field: FillField, regexPattern: RegExp, value: string | undefined) => {
      if (!value) {
        result.missing.push(field);
        return;
      }
      try {
        const containers = page.locator('div, label').filter({ hasText: regexPattern });
        const count = await containers.count();
        if (count > 0) {
           // We will take the last match as it's likely the most specific container
           const container = containers.last();
           const input = container.locator('..').locator('input[type="text"], input[type="url"]').first();
           if (await input.count() > 0) {
             if (await input.isDisabled()) {
                 result.skipped.push({ label: field, reason: 'disabled_or_readonly' });
                 return;
             }
             if (await input.inputValue()) {
                 result.skipped.push({ label: field, reason: 'already_filled' });
                 return;
             }
             await input.fill(value);
             result.filled.push({ field, label: field });
             return;
           }
        }
        result.missing.push(field);
      } catch (error) {
        result.skipped.push({ label: field, reason: 'error_filling' });
      }
    };

    if (profile.linkedin_url) await fillCustomLabel('linkedin_url', /linkedin/i, profile.linkedin_url);
    if (profile.github_url) await fillCustomLabel('github_url', /github/i, profile.github_url);
    if (profile.portfolio_url) await fillCustomLabel('portfolio_url', /portfolio|website/i, profile.portfolio_url);

    if (resumePath) {
      try {
        const fileInputs = page.locator('input[type="file"]');
        const count = await fileInputs.count();
        if (count > 0) {
          const resumeInput = fileInputs.first();
          await resumeInput.setInputFiles(resumePath);
          result.filled.push({ field: 'resume', label: 'resume' });
        } else {
          result.missing.push('resume');
        }
      } catch {
        result.skipped.push({ label: 'resume', reason: 'upload_failed' });
      }
    } else {
      result.missing.push('resume');
    }

    return result;
  }
}
