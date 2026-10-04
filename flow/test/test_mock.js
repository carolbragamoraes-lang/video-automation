// Roda flow_automation.js contra o mock local e confere o estado final.
const { execFile } = require("child_process");
const { promisify } = require("util");
const path = require("path");
const fs = require("fs");
const puppeteer = require("puppeteer-core");

const chrome = process.env.CHROME_PATH || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const root = path.join(__dirname, "..", "..");
const mock = "file://" + path.join(__dirname, "mock_flow.html");
const takesFile = path.join(root, "receita_bicarbonato", "flow_takes.json");
const spec = JSON.parse(fs.readFileSync(takesFile, "utf8"));

(async () => {
  // abre um Chromium com porta de depuração, como o Chrome do usuário, e deixa
  // o script principal se conectar a ele; depois lê o estado do mock
  const browser = await puppeteer.launch({ executablePath: chrome, headless: true, args: ["--no-sandbox", "--remote-debugging-port=9333"] });
  try {
    const { stdout } = await promisify(execFile)("node", [path.join(root, "flow", "flow_automation.js"), takesFile,
      "--browser-url", "http://127.0.0.1:9333", "--url", mock]);
    process.stdout.write(stdout);
    const pages = await browser.pages();
    const page = pages.find((p) => p.url().startsWith("file://"));
    const state = await page.evaluate(() => window.state);
    const fail = (m) => { console.error("FALHOU:", m); process.exitCode = 1; };
    if (state.jobs.length !== spec.takes.length) fail(`esperava ${spec.takes.length} gerações, houve ${state.jobs.length}`);
    state.jobs.forEach((j, i) => {
      if (j.aspect !== "9:16") fail(`take ${i + 1} em ${j.aspect}`);
      if (!j.prompt.startsWith(spec.takes[i].prompt.slice(0, 60))) fail(`prompt do take ${i + 1} diferente`);
      if (!/^Veo 3\.1/.test(j.model)) fail(`modelo ${j.model}`);
      if (j.outputs !== String(spec.config_flow.saidas_por_prompt)) fail(`saídas ${j.outputs}`);
    });
    if (state.mode !== "Text to Video") fail(`modo ${state.mode}`);
    if (!process.exitCode) console.log(`OK: ${state.jobs.length} takes enviados em 9:16 (${state.jobs[0].model}, ${state.jobs[0].outputs} saídas)`);
  } finally {
    await browser.close();
  }
})();
