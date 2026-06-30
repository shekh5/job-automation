import type { Page } from 'playwright';
import type { AtsHandler } from './types';
import { LeverHandler } from './lever';
import { GreenhouseHandler } from './greenhouse';
import { AshbyHandler } from './ashby';

const HANDLERS: AtsHandler[] = [
  new LeverHandler(),
  new GreenhouseHandler(),
  new AshbyHandler()
];

export function registerAtsHandler(handler: AtsHandler) {
  HANDLERS.push(handler);
}

export async function detectAts(url: string, page: Page): Promise<AtsHandler | null> {
  for (const handler of HANDLERS) {
    if (await handler.detect(url, page)) {
      return handler;
    }
  }
  return null;
}
