import type { Page } from 'playwright';
import type { AtsHandler } from './types';
import type { ApplicantProfile, FillResult, FillField } from '../formFiller';

export class LeverHandler implements AtsHandler {
  name = 'lever';

  async detect(url: string, page: Page): Promise<boolean> {
    try {
      const parsedUrl = new URL(url);
      if (parsedUrl.hostname === 'jobs.lever.co' || parsedUrl.hostname.endsWith('.lever.co')) {
        return true;
      }
      
      const isLever = await page.evaluate(() => {
        return window.location.href.includes('lever.co') 
          || document.querySelector('form[action*="lever.co"]') !== null;
      });
      return isLever;
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

    if (profile.full_name) {
      await attemptFill('full_name', 'input[name="name"]', profile.full_name);
    } else if (profile.first_name || profile.last_name) {
      await attemptFill('full_name', 'input[name="name"]', `${profile.first_name || ''} ${profile.last_name || ''}`.trim());
    } else {
      result.missing.push('full_name');
    }

    await attemptFill('email', 'input[name="email"]', profile.email);
    await attemptFill('phone', 'input[name="phone"]', profile.phone);
    await attemptFill('location', 'input[name="org"]', profile.location); // org or current company
    
    // Lever uses custom URLs sections. We'll try common names
    if (profile.linkedin_url) {
      await attemptFill('linkedin_url', 'input[name="urls[LinkedIn]"]', profile.linkedin_url);
    }
    if (profile.github_url) {
      await attemptFill('github_url', 'input[name="urls[GitHub]"]', profile.github_url);
    }
    if (profile.portfolio_url) {
      await attemptFill('portfolio_url', 'input[name="urls[Portfolio]"]', profile.portfolio_url);
    }

    if (resumePath) {
      try {
        const resumeInput = page.locator('input[type="file"][data-qa="resume-upload"], input[name="resume"]');
        if (await resumeInput.count() > 0) {
          await resumeInput.first().setInputFiles(resumePath);
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
