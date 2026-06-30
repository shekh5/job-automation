import type { Page } from 'playwright';
import type { AtsHandler } from './types';
import type { ApplicantProfile, FillResult, FillField } from '../formFiller';

export class GreenhouseHandler implements AtsHandler {
  name = 'greenhouse';

  async detect(url: string, page: Page): Promise<boolean> {
    try {
      const parsedUrl = new URL(url);
      if (parsedUrl.hostname === 'boards.greenhouse.io' || parsedUrl.hostname.endsWith('.greenhouse.io')) {
        return true;
      }
      
      const isGreenhouse = await page.evaluate(() => {
        return document.querySelector('#application_form') !== null 
          || window.location.href.includes('greenhouse.io');
      });
      return isGreenhouse;
    } catch {
      return false;
    }
  }

  async fill(page: Page, profile: ApplicantProfile, resumePath?: string): Promise<FillResult> {
    try {
      // Wait for React SPAs (like job-boards.greenhouse.io) to mount the inputs
      await page.waitForSelector('input#first_name, input[name="job_application[first_name]"]', { timeout: 10000 });
    } catch {
      // Ignore if it times out
    }
    const result: FillResult = {
      filled: [],
      missing: [],
      skipped: [],
    };

    const extendedProfile = profile as ApplicantProfile & Record<string, string | undefined>;

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

    await attemptFill('first_name', 'input#first_name, input[name="job_application[first_name]"]', profile.first_name);
    await attemptFill('last_name', 'input#last_name, input[name="job_application[last_name]"]', profile.last_name);
    await attemptFill('email', 'input#email, input[name="job_application[email]"]', profile.email);
    await attemptFill('phone', 'input#phone, input[name="job_application[phone]"]', profile.phone);
    
    // Greenhouse custom questions often have specific labels or predictable text patterns for LinkedIn, Github, Portfolio
    // We'll use broader locator matching for those if they aren't standard.
    const fillCustomUrl = async (field: FillField, regexPattern: RegExp, value: string | undefined) => {
      if (!value) {
        result.missing.push(field);
        return;
      }
      try {
        const customFields = page.locator('.custom_question');
        const count = await customFields.count();
        for (let i = 0; i < count; i++) {
          const customField = customFields.nth(i);
          const labelText = await customField.locator('label').innerText().catch(() => '');
          if (regexPattern.test(labelText)) {
            const input = customField.locator('input[type="text"]');
            if (await input.count() > 0) {
               if (await input.first().isDisabled()) {
                 result.skipped.push({ label: field, reason: 'disabled_or_readonly' });
                 return;
               }
               if (await input.first().inputValue()) {
                 result.skipped.push({ label: field, reason: 'already_filled' });
                 return;
               }
               await input.first().fill(value);
               result.filled.push({ field, label: field });
               return;
            }
          }
        }
        result.missing.push(field);
      } catch (error) {
        result.skipped.push({ label: field, reason: 'error_filling' });
      }
    };

    if (profile.linkedin_url) await fillCustomUrl('linkedin_url', /linkedin/i, profile.linkedin_url);
    if (profile.github_url) await fillCustomUrl('github_url', /github/i, profile.github_url);
    if (profile.portfolio_url) await fillCustomUrl('portfolio_url', /portfolio|website/i, profile.portfolio_url);

    const fillBySelector = async (field: FillField, selector: string, value: string | undefined) => {
      if (!value) return;
      try {
        const input = page.locator(selector).first();
        if ((await input.count()) === 0) return;
        if (await input.isDisabled()) {
          result.skipped.push({ label: field, reason: 'disabled_or_readonly' });
          return;
        }
        if (await input.inputValue()) {
          result.skipped.push({ label: field, reason: 'already_filled' });
          return;
        }
        await input.fill(value);
        result.missing = result.missing.filter(item => item !== field);
        result.filled.push({ field, label: field });
      } catch {
        result.skipped.push({ label: field, reason: 'error_filling' });
      }
    };

    const selectReactOption = async (label: string, selector: string, value: string | undefined) => {
      if (!value) {
        result.missing.push(label as FillField);
        return;
      }
      try {
        const input = page.locator(selector).first();
        if ((await input.count()) === 0) {
          result.missing.push(label as FillField);
          return;
        }
        await input.click();
        await input.fill(value);
        await page.keyboard.press('Enter');
        result.missing = result.missing.filter(item => item !== label as FillField);
        result.filled.push({ field: label as FillField, label });
      } catch {
        result.skipped.push({ label, reason: 'error_selecting' });
      }
    };

    await fillBySelector('linkedin_url', 'input#question_36101205002', profile.linkedin_url);
    await fillBySelector('first_name', 'input#question_36101206002', profile.first_name || profile.full_name);
    await fillBySelector('location', 'input#question_36101208002', extendedProfile.accessibility_adjustments || 'None');

    await selectReactOption('employment_restrictions', 'input#question_36101207002', extendedProfile.employment_restrictions || 'No');
    await selectReactOption('visa_sponsorship', 'input#question_36101209002', extendedProfile.visa_sponsorship || 'No');
    await selectReactOption('previous_gitlab', 'input#question_36101210002', extendedProfile.previous_gitlab || 'No');
    await selectReactOption('country_residence', 'input#question_36101211002', extendedProfile.country_residence || profile.location || 'India');

    if (resumePath) {
      try {
        const fileInputs = page.locator('input#resume, input[type="file"][name="job_application[resume]"]');
        const count = await fileInputs.count();
        if (count > 0) {
          // Greenhouse often has multiple file inputs depending on "Upload", "Dropbox", "Google Drive" buttons
          // Usually the direct file upload input works
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
