#!/usr/bin/env node
/*
 * Automação do Google Flow (https://labs.google/fx/tools/flow) com Puppeteer.
 *
 * Lê um <projeto>/flow_takes.json, cria um projeto novo no Flow em 9:16,
 * cola o prompt de cada take e dispara a geração.
 *
 * O Flow exige login Google, por isso o script se conecta ao SEU Chrome já
 * logado (via porta de depuração) em vez de abrir um navegador anônimo.
 *
 *   1) Abra um Chrome dedicado com depuração remota (só na 1ª vez faça login
 *      no Google nessa janela; o perfil fica salvo em ~/.flow-chrome):
 *        macOS:   "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
 *                   --remote-debugging-port=9222 --user-data-dir="$HOME/.flow-chrome"
 *        Windows: "C:\Program Files\Google\Chrome\Application\chrome.exe" ^
 *                   --remote-debugging-port=9222 --user-data-dir="%USERPROFILE%\.flow-chrome"
 *   2) npm install
 *   3) node flow/flow_automation.js receita_bicarbonato/flow_takes.json
 *
 * Opções:
 *   --browser-url URL   endpoint de depuração (padrão http://127.0.0.1:9222)
 *   --launch PATH       abre um Chromium próprio em vez de conectar (testes)
 *   --url URL           URL do Flow (padrão https://labs.google/fx/tools/flow)
 *   --only T1,T3        gera só esses takes
 *   --no-generate       cola os prompts mas não clica em gerar
 *   --dry-run           só imprime o que seria feito, sem abrir navegador
 *   --manual            usa a aba do Flow já aberta, onde você mesmo criou o
 *                       projeto e escolheu 9:16/Veo 3.1; o script só cola e gera
 *
 * Em caso de erro, o script salva flow_screens/erro.png e flow_screens/erro_botoes.txt
 * (lista de botões visíveis) para ajustar flow/selectors.json.
 *
 * A interface do Flow muda com frequência. Os textos/seletores procurados
 * ficam em flow/selectors.json e podem ser ajustados sem mexer no código.
 */
const fs = require("fs");
const path = require("path");

const SELECTORS = JSON.parse(
  fs.readFileSync(path.join(__dirname, "selectors.json"), "utf8")
);

function parseArgs(argv) {
  const opts = {
    browserUrl: "http://127.0.0.1:9222",
    url: "https://labs.google/fx/tools/flow",
    generate: true,
    dryRun: false,
    launch: null,
    only: null,
    takesFile: null,
    manual: false,
  };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--browser-url") opts.browserUrl = argv[++i];
    else if (a === "--url") opts.url = argv[++i];
    else if (a === "--launch") opts.launch = argv[++i];
    else if (a === "--only") opts.only = argv[++i].split(",");
    else if (a === "--no-generate") opts.generate = false;
    else if (a === "--dry-run") opts.dryRun = true;
    else if (a === "--manual") opts.manual = true;
    else if (!opts.takesFile) opts.takesFile = a;
    else throw new Error(`Argumento desconhecido: ${a}`);
  }
  if (!opts.takesFile) {
    throw new Error("Uso: node flow/flow_automation.js <projeto>/flow_takes.json [opções]");
  }
  return opts;
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const log = (...m) => console.log(`[flow ${new Date().toLocaleTimeString()}]`, ...m);

// Regra de legendas (CLAUDE.md): nunca pedir "no text"/"no subtitles"; todo
// take traz a narração exata como legenda embutida.
function checkSubtitleRule(take) {
  const all = `${take.prompt}\n${take.negative_prompt || ""}`;
  const banned = all.match(/\bno\s+(on-?screen\s+)?(text|subtitles?|captions?)\b/i);
  if (banned) throw new Error(`${take.id}: o prompt contém "${banned[0]}", proibido pela regra de legendas.`);
  if (/\b(text|subtitles?|captions?)\b/i.test(take.negative_prompt || "")) {
    throw new Error(`${take.id}: negative_prompt não pode excluir texto/legendas.`);
  }
  const fala = (take.prompt.match(/says:\s*"([^"]+)"/) || [])[1];
  const legenda = (take.prompt.match(/subtitle overlay:\s*"([^"]+)"/) || [])[1];
  if (!legenda) throw new Error(`${take.id}: falta a linha 'Centered lower-third modern bold subtitle overlay: "..."'.`);
  if (fala && fala !== legenda) throw new Error(`${take.id}: a legenda não é idêntica à narração.`);
}

function buildPrompt(spec, take) {
  checkSubtitleRule(take);
  // O Flow tem um único campo de texto: o negativo vai como instrução "Avoid:".
  let p = take.prompt.trim();
  if (take.negative_prompt) p += `\nAvoid: ${take.negative_prompt}.`;
  return p;
}

/* ---------- helpers que rodam dentro da página ---------- */

// Procura um elemento clicável cujo texto, aria-label ou title bata com algum
// dos padrões (regex, sem diferenciar maiúsculas). Retorna o handle ou null.
async function findClickable(page, patterns, { scope = null } = {}) {
  const handle = await page.evaluateHandle(
    (patterns, scope) => {
      const res = patterns.map((p) => new RegExp(p, "i"));
      const root = scope ? document.querySelector(scope) || document : document;
      const nodes = root.querySelectorAll(
        'button, [role="button"], [role="menuitem"], [role="option"], [role="tab"], [role="radio"], a, li, mat-option'
      );
      const visible = (el) => {
        const r = el.getBoundingClientRect();
        const s = getComputedStyle(el);
        return r.width > 0 && r.height > 0 && s.visibility !== "hidden" && s.display !== "none";
      };
      for (const re of res) {
        for (const el of nodes) {
          if (!visible(el) || el.disabled) continue;
          const label = [el.innerText, el.getAttribute("aria-label"), el.getAttribute("title")]
            .filter(Boolean)
            .join(" ")
            .trim();
          if (label && re.test(label)) return el;
        }
      }
      return null;
    },
    patterns,
    scope
  );
  const el = handle.asElement();
  if (!el) await handle.dispose();
  return el;
}

async function clickByText(page, patterns, what, { optional = false, timeout = 15000 } = {}) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeout) {
    const el = await findClickable(page, patterns);
    if (el) {
      await el.evaluate((e) => e.scrollIntoView({ block: "center" }));
      await el.click();
      log(`clicou: ${what}`);
      return true;
    }
    await sleep(500);
  }
  if (optional) {
    log(`(opcional) não encontrado: ${what}`);
    return false;
  }
  throw new Error(`Não encontrei "${what}" (padrões: ${patterns.join(" | ")}). Ajuste flow/selectors.json.`);
}

async function findPromptBox(page, timeout = 20000) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeout) {
    for (const sel of SELECTORS.promptBox) {
      const els = await page.$$(sel);
      for (const el of els) {
        const ok = await el.evaluate((e) => {
          const r = e.getBoundingClientRect();
          return r.width > 50 && r.height > 10 && !e.disabled && !e.readOnly;
        });
        if (ok) return el;
      }
    }
    await sleep(500);
  }
  throw new Error("Não encontrei a caixa de prompt do Flow. Ajuste 'promptBox' em flow/selectors.json.");
}

async function pastePrompt(page, box, text) {
  await box.evaluate((e) => e.scrollIntoView({ block: "center" }));
  await box.click();
  const isEditable = await box.evaluate((e) => e.isContentEditable);
  if (isEditable) {
    // contenteditable: seleciona tudo e insere via execCommand (dispara os eventos do framework)
    await box.evaluate((e, text) => {
      e.focus();
      document.execCommand("selectAll", false, null);
      document.execCommand("insertText", false, text);
    }, text);
  } else {
    // textarea/input: usa o setter nativo para o React/Angular perceberem a mudança
    await box.evaluate((e, text) => {
      const proto = e.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
      Object.getOwnPropertyDescriptor(proto, "value").set.call(e, text);
      e.dispatchEvent(new Event("input", { bubbles: true }));
      e.dispatchEvent(new Event("change", { bubbles: true }));
    }, text);
  }
  // um caractere digitado "de verdade" garante que o botão de gerar habilite
  await page.keyboard.type(" ");
  await page.keyboard.press("Backspace");
}

async function setAspect916(page) {
  const pick = () => clickByText(page, SELECTORS.aspect916, "proporção 9:16", { optional: true, timeout: 3000 });
  if (await pick()) return; // opção já visível
  if (await clickByText(page, SELECTORS.aspectMenu, "seletor de proporção", { optional: true, timeout: 3000 })) {
    await sleep(400);
    if (await pick()) return;
  }
  // painel de configurações fechado: abre e tenta de novo
  if (await clickByText(page, SELECTORS.settings, "configurações", { optional: true, timeout: 3000 })) {
    await sleep(600);
    if (await pick()) return;
    if (await clickByText(page, SELECTORS.aspectMenu, "seletor de proporção", { optional: true, timeout: 3000 })) {
      await sleep(400);
      if (await pick()) return;
    }
  }
  throw new Error("Não consegui selecionar 9:16. Selecione manualmente ou ajuste 'aspect916'/'aspectMenu' em flow/selectors.json.");
}

async function setOptional(page, openerPatterns, valuePatterns, what) {
  if (await clickByText(page, valuePatterns, what, { optional: true, timeout: 1500 })) return;
  if (await clickByText(page, openerPatterns, `menu ${what}`, { optional: true, timeout: 2500 })) {
    await sleep(400);
    await clickByText(page, valuePatterns, what, { optional: true, timeout: 3000 });
    await page.keyboard.press("Escape").catch(() => {});
  }
}

// Lista o texto/aria-label de tudo que é clicável na tela (para diagnóstico).
async function dumpUi(page, file) {
  const items = await page.evaluate(() => {
    const out = [];
    const nodes = document.querySelectorAll(
      'button, [role="button"], [role="menuitem"], [role="option"], [role="tab"], [role="radio"], [role="combobox"], [role="listbox"], a, select, textarea, [contenteditable="true"]'
    );
    for (const el of nodes) {
      const r = el.getBoundingClientRect();
      if (!r.width || !r.height) continue;
      const txt = (el.innerText || el.value || "").replace(/\s+/g, " ").trim().slice(0, 80);
      const aria = el.getAttribute("aria-label") || "";
      const ph = el.getAttribute("placeholder") || "";
      out.push(`${el.tagName.toLowerCase()}${el.getAttribute("role") ? `[role=${el.getAttribute("role")}]` : ""} | texto="${txt}" | aria="${aria}"${ph ? ` | placeholder="${ph}"` : ""} | pos=${Math.round(r.x)},${Math.round(r.y)}`);
    }
    return out;
  });
  fs.writeFileSync(file, `URL: ${page.url()}\n` + items.join("\n") + "\n");
}

/* ---------- fluxo principal ---------- */

async function main() {
  const opts = parseArgs(process.argv.slice(2));
  const spec = JSON.parse(fs.readFileSync(opts.takesFile, "utf8"));
  let takes = spec.takes;
  if (opts.only) takes = takes.filter((t) => opts.only.includes(t.id));
  if (!takes.length) throw new Error("Nenhum take para gerar.");

  const cfg = spec.config_flow || {};
  if ((cfg.proporcao || "9:16") !== "9:16") log(`aviso: proporcao=${cfg.proporcao}, forçando 9:16`);

  if (opts.dryRun) {
    log(`projeto: ${spec.projeto} | modelo: ${cfg.modelo || "padrão"} | 9:16 | ${takes.length} take(s)`);
    for (const t of takes) console.log(`\n--- ${t.id} (${t.inicio_s}-${t.fim_s}s) ---\n${buildPrompt(spec, t)}`);
    return;
  }

  const puppeteer = require("puppeteer-core");
  const browser = opts.launch
    ? await puppeteer.launch({ executablePath: opts.launch, headless: true, args: ["--no-sandbox"] })
    : await puppeteer.connect({ browserURL: opts.browserUrl, defaultViewport: null });

  const outDir = path.join(path.dirname(path.resolve(opts.takesFile)), "flow_screens");
  fs.mkdirSync(outDir, { recursive: true });
  const shot = (page, name) => page.screenshot({ path: path.join(outDir, `${name}.png`) }).catch(() => {});

  let page;
  if (opts.manual) {
    // usa a aba do Flow que você já deixou configurada
    const pages = (await browser.pages()).filter((p) => p.url().includes("/tools/flow") || p.url().startsWith(opts.url));
    page = pages.find((p) => /\/project/.test(p.url())) || pages[pages.length - 1];
    if (!page) throw new Error("Modo --manual: abra o projeto do Flow numa aba desse Chrome e rode de novo.");
    await page.bringToFront();
    log(`usando a aba aberta: ${page.url()}`);
  } else {
    page = await browser.newPage();
  }
  page.setDefaultTimeout(30000);
  failPage = page;
  failDir = outDir;

  if (!opts.manual) {
    log(`abrindo ${opts.url}`);
    await page.goto(opts.url, { waitUntil: "domcontentloaded", timeout: 60000 });
    await sleep(3000); // o Flow é uma SPA com conexões abertas: espera a UI montar

    if (/accounts\.google\.com/.test(page.url())) {
      throw new Error("O Flow pediu login. Faça login no Google nessa janela do Chrome e rode de novo.");
    }

    // 1) novo projeto
    await clickByText(page, SELECTORS.newProject, "Novo projeto");
    await sleep(2500);
    await dumpUi(page, path.join(outDir, "projeto_botoes.txt"));
    await shot(page, "00_projeto");

    // 2) modo texto→vídeo, modelo, proporção 9:16, nº de saídas
    await setOptional(page, SELECTORS.modeMenu, SELECTORS.textToVideo, "modo Text to Video");
    await clickByText(page, SELECTORS.settings, "configurações", { optional: true, timeout: 4000 });
    await sleep(600);
    await dumpUi(page, path.join(outDir, "config_botoes.txt"));
    await shot(page, "00_config_aberta");
    if (cfg.modelo) {
      const modelRe = [cfg.modelo.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")];
      await setOptional(page, SELECTORS.modelMenu, modelRe, `modelo ${cfg.modelo}`);
    }
    await setAspect916(page);
    if (cfg.saidas_por_prompt) {
      await setOptional(page, SELECTORS.outputsMenu, [`^\\s*${cfg.saidas_por_prompt}\\s*$`], `${cfg.saidas_por_prompt} saída(s)`);
    }
    await shot(page, "00_config");
  }

  // 3) para cada take: cola o prompt e dispara a geração
  for (const take of takes) {
    const prompt = buildPrompt(spec, take);
    const box = await findPromptBox(page);
    await pastePrompt(page, box, prompt);
    log(`${take.id}: prompt colado (${prompt.length} caracteres)`);
    await shot(page, `${take.id}_prompt`);
    if (opts.generate) {
      await clickByText(page, SELECTORS.generate, `gerar ${take.id}`, { timeout: 10000 });
      log(`${take.id}: geração iniciada`);
      await sleep(4000); // deixa o Flow enfileirar antes do próximo prompt
      await shot(page, `${take.id}_gerando`);
    }
  }

  log(`pronto. Prints em ${outDir}. As cenas continuam gerando no Flow (acompanhe na aba aberta).`);
  if (opts.launch) await browser.close();
  else browser.disconnect();
}

let failPage = null;
let failDir = null;

main().catch(async (err) => {
  console.error(`[flow] ERRO: ${err.message}`);
  if (failPage && failDir) {
    await failPage.screenshot({ path: path.join(failDir, "erro.png") }).catch(() => {});
    await dumpUi(failPage, path.join(failDir, "erro_botoes.txt")).catch(() => {});
    console.error(`[flow] diagnóstico salvo em ${failDir}/erro.png e erro_botoes.txt`);
    console.error("[flow] dica: configure 9:16 e Veo 3.1 à mão na aba do Flow e rode de novo com --manual");
  }
  process.exit(1);
});
