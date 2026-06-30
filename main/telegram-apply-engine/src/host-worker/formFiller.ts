import type { Page } from 'playwright';

export interface ApplicantProfile {
  first_name?: string;
  last_name?: string;
  full_name?: string;
  email?: string;
  phone?: string;
  location?: string;
  linkedin_url?: string;
  github_url?: string;
  portfolio_url?: string;
}

export type FillField = keyof ApplicantProfile | 'resume';

export interface FillResult {
  filled: Array<{ field: FillField; label: string }>;
  missing: Array<FillField>;
  skipped: Array<{ label: string; reason: string }>;
}

type ProfileField = keyof ApplicantProfile;

const FIELD_PATTERNS: Array<{ field: ProfileField; patterns: RegExp[] }> = [
  { field: 'first_name', patterns: [/first\s*name/, /given\s*name/] },
  { field: 'last_name', patterns: [/last\s*name/, /family\s*name/, /surname/] },
  { field: 'full_name', patterns: [/full\s*name/, /^name$/] },
  { field: 'email', patterns: [/e-?mail/, /email\s*address/] },
  { field: 'phone', patterns: [/phone/, /mobile/, /telephone/] },
  { field: 'location', patterns: [/location/, /city/, /address/] },
  { field: 'linkedin_url', patterns: [/linkedin/, /linked\s*in/] },
  { field: 'github_url', patterns: [/github/, /git\s*hub/] },
  { field: 'portfolio_url', patterns: [/portfolio/, /website/, /personal\s*site/] },
];

function compactText(value: string | null | undefined) {
  return (value || '')
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase();
}

async function fillResumeField(page: Page, resumePath: string | undefined, result: FillResult) {
  const fileInputs = await page.locator('input[type="file"]').evaluateAll((elements) => {
    return elements.map((element, index) => {
      let labelText = '';
      const id = element.getAttribute('id');
      if (id) {
        const label = document.querySelector(`label[for="${CSS.escape(id)}"]`);
        if (label?.textContent) labelText = label.textContent;
      }
      if (!labelText) {
        const wrappingLabel = element.closest('label');
        if (wrappingLabel?.textContent) labelText = wrappingLabel.textContent;
      }
      if (!labelText) {
        const parentLabel = element.parentElement?.querySelector('label');
        if (parentLabel?.textContent) labelText = parentLabel.textContent;
      }

      const input = element as HTMLInputElement;
      return {
        index,
        label: labelText,
        ariaLabel: input.getAttribute('aria-label') || '',
        name: input.getAttribute('name') || '',
        id: input.getAttribute('id') || '',
        accept: input.getAttribute('accept') || '',
        disabled: input.disabled,
      };
    });
  });

  if (fileInputs.length === 0) {
    if (resumePath) {
      result.missing.push('resume');
    }
    return;
  }

  if (!resumePath) {
    result.missing.push('resume');
    return;
  }

  const candidates = fileInputs.map(input => ({
    ...input,
    searchable: compactText([
      input.label,
      input.ariaLabel,
      input.name,
      input.id,
      input.accept,
    ].join(' ')),
  }));

  const resumeCandidates = candidates.filter(input => /resume|cv|curriculum\s*vitae/.test(input.searchable));
  const selected = fileInputs.length === 1 ? candidates[0] : resumeCandidates.length === 1 ? resumeCandidates[0] : null;

  if (!selected) {
    result.skipped.push({ label: 'resume upload', reason: 'ambiguous_file_input' });
    return;
  }

  if (selected.disabled) {
    result.skipped.push({ label: selected.searchable || 'resume upload', reason: 'disabled_file_input' });
    return;
  }

  try {
    await page.locator('input[type="file"]').nth(selected.index).setInputFiles(resumePath);
    result.filled.push({ field: 'resume', label: selected.searchable || 'resume upload' });
  } catch {
    result.skipped.push({ label: selected.searchable || 'resume upload', reason: 'upload_failed' });
  }
}

export async function fillCommonFields(page: Page, profile: ApplicantProfile, resumePath?: string): Promise<FillResult> {
  const result: FillResult = {
    filled: [],
    missing: [],
    skipped: [],
  };

  const fields = await page.locator('input, textarea').evaluateAll((elements) => {
    return elements.map((element, index) => {
      let labelText = '';
      const id = element.getAttribute('id');
      if (id) {
        const label = document.querySelector(`label[for="${CSS.escape(id)}"]`);
        if (label?.textContent) labelText = label.textContent;
      }
      if (!labelText) {
        const wrappingLabel = element.closest('label');
        if (wrappingLabel?.textContent) labelText = wrappingLabel.textContent;
      }
      if (!labelText) {
        const parentLabel = element.parentElement?.querySelector('label');
        if (parentLabel?.textContent) labelText = parentLabel.textContent;
      }

      const input = element as HTMLInputElement | HTMLTextAreaElement;
      return {
        index,
        tag: input.tagName.toLowerCase(),
        type: input instanceof HTMLInputElement ? (input.type || 'text').toLowerCase() : 'textarea',
        label: labelText,
        placeholder: input.getAttribute('placeholder') || '',
        ariaLabel: input.getAttribute('aria-label') || '',
        name: input.getAttribute('name') || '',
        id: input.getAttribute('id') || '',
        disabled: input.disabled,
        readOnly: input.readOnly,
        value: input.value,
      };
    });
  });

  const filledFields = new Set<ProfileField>();

  for (const field of fields) {
    const searchable = compactText([
      field.label,
      field.placeholder,
      field.ariaLabel,
      field.name,
      field.id,
    ].join(' '));

    if (field.disabled || field.readOnly) {
      result.skipped.push({ label: searchable || `field_${field.index}`, reason: 'disabled_or_readonly' });
      continue;
    }

    if (field.tag === 'input' && field.type === 'file') {
      continue;
    }

    if (field.tag === 'input' && !['text', 'email', 'tel', 'url', 'search'].includes(field.type)) {
      result.skipped.push({ label: searchable || `field_${field.index}`, reason: `unsupported_type_${field.type}` });
      continue;
    }

    const match = FIELD_PATTERNS.find(({ field: profileField, patterns }) => {
      if (filledFields.has(profileField)) return false;
      return patterns.some(pattern => pattern.test(searchable));
    });

    if (!match) continue;

    const value = profile[match.field];
    if (!value) {
      if (!result.missing.includes(match.field)) {
        result.missing.push(match.field);
      }
      continue;
    }

    const locator = page.locator('input, textarea').nth(field.index);
    const currentValue = await locator.inputValue();
    if (currentValue) {
      result.skipped.push({ label: match.field, reason: 'already_filled' });
      filledFields.add(match.field);
      continue;
    }

    await locator.fill(value);
    filledFields.add(match.field);
    result.filled.push({ field: match.field, label: searchable || `field_${field.index}` });
  }

  for (const field of FIELD_PATTERNS.map(item => item.field)) {
    if (profile[field] && !filledFields.has(field)) {
      result.missing.push(field);
    }
  }

  await fillResumeField(page, resumePath, result);

  return result;
}
