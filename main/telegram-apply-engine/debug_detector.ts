import { chromium } from 'playwright';
import { detectAts } from './src/host-worker/ats/detector';
import { GreenhouseHandler } from './src/host-worker/ats/greenhouse';

async function main() {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  
  console.log("Checking GreenhouseHandler directly...");
  const greenhouse = new GreenhouseHandler();
  const url = "https://job-boards.greenhouse.io/gitlab/jobs/8503792002";
  const result1 = await greenhouse.detect(url, page);
  console.log("GreenhouseHandler.detect:", result1);

  console.log("Checking detectAts...");
  const handler = await detectAts(url, page);
  console.log("detectAts returned:", handler ? handler.name : "null");

  await browser.close();
}

main().catch(console.error);
