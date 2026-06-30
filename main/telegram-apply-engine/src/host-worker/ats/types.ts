import type { Page } from 'playwright';
import type { ApplicantProfile, FillResult } from '../formFiller';

export interface AtsHandler {
  name: string;
  detect(url: string, page: Page): Promise<boolean>;
  fill(page: Page, profile: ApplicantProfile, resumePath?: string): Promise<FillResult>;
}
