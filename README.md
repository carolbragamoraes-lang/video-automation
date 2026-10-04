# video-automation

- `flow/`: automação do Google Flow (Veo 3.1) com Puppeteer. Veja `CLAUDE.md`.
- `receita_bicarbonato/`: projeto exemplo (análise, takes, copy e vídeo ilustrado).

```bash
npm install
# 1x: abra um Chrome com depuração e faça login no Google nessa janela
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --remote-debugging-port=9222 --user-data-dir="$HOME/.flow-chrome"
# confira e envie os takes para o Flow
node flow/flow_automation.js receita_bicarbonato/flow_takes.json --dry-run
node flow/flow_automation.js receita_bicarbonato/flow_takes.json
```
