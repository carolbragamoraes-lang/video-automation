# video-automation

## Pipeline padrão: vídeo de referência → Google Flow

Sempre que um novo vídeo de referência for enviado para análise, siga estes passos:

1. **Extrair**: `flow/extrair_referencia.sh <video> <projeto>/` gera
   `referencia/grid.png` (1 quadro/s) e os metadados. Leia o grid para a análise.
2. **Estrutura**: crie `<projeto>/flow_takes.json` no mesmo formato de
   `receita_bicarbonato/flow_takes.json`:
   - `analise`: formato, cenário, ações por segundo, estrutura da copy, riscos, diferenciação;
   - `config_flow`: `modelo: "Veo 3.1"`, `proporcao: "9:16"`, `modo: "Text to Video"`;
   - `takes`: blocos de **8 s** (duração máxima de um clip do Veo 3.1). Cada
     prompt deve ser autossuficiente, repetir cenário, luz e câmera para manter a
     continuidade, incluir a fala/áudio entre aspas ("Audio: ... says: \"...\"") e
     pedir "no text, no logos". As legendas entram na pós-produção, não no Veo.
3. **Copy**: nova e em inglês (salvo pedido contrário), terminando com o CTA
   `COMMENT "YES"`. Mude cenário e detalhes visuais em relação à referência
   para não ser cópia. Nunca invente médico, estudo, depoimento ou promessa de
   cura/resultado em X dias. Mantenha o aviso "For informational purposes only.
   Not medical advice." quando o tema tocar em saúde.
4. **Flow**: `node flow/flow_automation.js <projeto>/flow_takes.json` cria o
   projeto 9:16, cola os prompts e inicia a geração. Antes, valide com
   `--dry-run` e `npm run flow:test` (mock local).
   - O container da nuvem **não alcança** labs.google e não tem login Google.
     Nesse caso, gere os arquivos, faça commit e diga ao usuário para rodar o
     passo 4 no computador dele (instruções no topo de `flow/flow_automation.js`).
   - Se a interface do Flow mudar, ajuste `flow/selectors.json`.

## Vídeo com legendas (sem IA)

`receita_bicarbonato/gerar_video.py` renderiza um vídeo ilustrado com legenda
palavra a palavra. A copy fica na lista `COPY`. Use-o como modelo para a
legendagem na pós-produção dos takes do Flow.
