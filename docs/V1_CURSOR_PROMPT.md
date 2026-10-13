# FireWatch AI — V1: From a Form to a Traceable Workflow

The V0 screenshot represents a simple local Cursor simulation. The GitHub implementation already contains the modular backend, storage, trace and optional Gemini adapter. V1 makes those component outputs readable and exposes a typed completed-run Shared State snapshot.

V1 is a presentation milestone; package version is 1.1.0. It is not a claim of real-world deployment or newly validated fire science. The State tab displays completed results, not intermediate live agent messages.

## Prompt for your existing V0 in Cursor

Copy the following into Cursor with your existing V0 project open. This adapts the working local code; it must not assume the local folder matches GitHub.

```text
Vamos evoluir o FireWatch AI — V0 Simulation para V1, seguindo o padrão
do ResilientCity AI: componentes dependentes, estado validado, evidências
rastreáveis, revisão crítica, Safety Gate e relatório explicável.

Primeiro leia os arquivos existentes e preserve a V0 funcional.
Use Python, Tkinter/ttk e Pydantic. Interface em inglês e explicações
em português. Não copie cegamente outro projeto nem remova testes válidos.

V1 deve executar componentes separados: Planner, Evidence, Fire Assessment,
Risk/Exposure, Decision, Critic, Safety Gate e Reporter. Human Gate registra
a revisão de uma pessoa; não é um LLM. As saídas posteriores dependem das
anteriores. Use modelos validados, IDs de evidência e run_id por execução.

Preserve a representação de unknown da V0: None não pode virar False.
Se adotar a enumeração yes/no/unknown usada no backend GitHub, faça uma
conversão explícita e testada, sem alterar o significado dos dados.

Nesta etapa use modo determinístico por padrão, sem novas chamadas de API.
Identifique-o honestamente como reference pipeline, não raciocínio por LLM.
Se já existir Gemini opcional, preserve seu modo separado e o fallback.

Adicione abas Incident, Agents, Evidence, Safety / Review, Report, Trace,
State e Evaluation. Agents mostra saídas legíveis e o modo real de cada
componente. State mostra um snapshot validado do estado final, preservando
observações, lacunas, propostas, crítica e regras de segurança.

Registre eventos reais em JSONL e resultados em SQLite. Workers não podem
atualizar Tk diretamente; conexões SQLite pertencem à thread correspondente.
Inclua histórico e exportação TXT/JSON. Aprovação humana não apaga Safety Gate.

Regras educacionais: chamas relatadas -> STRONG_INDICATION; fumaça sem
chamas relatadas -> POSSIBLE_FIRE; fumaça e chamas explicitamente ausentes
-> NO_INDICATION no relato; dados parciais -> INSUFFICIENT_EVIDENCE.
Indícios com pessoas/infraestrutura expostas -> HIGH e revisão humana.
Exposição desconhecida com indícios -> UNDETERMINED e revisão humana.
Indícios sem exposição relatada -> MEDIUM e revisão humana.
Lacunas relevantes, conflitos sinalizados, dados antigos, crítica pendente
ou fallback -> revisão humana. Nenhum resultado equivale a área segura.

Não adicione percentuais de confiança, previsão de propagação ou imagens
tratadas como detecção real. Não invente fontes. Limite a crítica a uma
revisão; se continuar rejeitando, encerre com revisão humana obrigatória.

Teste unknown, valores inválidos, chamas com exposição, limite de revisão,
trace real, persistência e aprovação humana preservando motivos de segurança.
Ao terminar explique o que mudou, resultados reais dos testes, comandos
Windows e quais verificações visuais ainda precisam ser feitas por mim.
```

## Acceptance on Windows

1. Analyze unknown indicators: uncertainty and required review remain visible in Agents and State.
2. Analyze reported flames with exposure: STRONG_INDICATION / HIGH / REQUIRED.
3. Inspect Trace: actual component events share the run ID shown in State.
4. Record a human approval: State adds the review, retaining the Safety Gate reasons.
5. Relaunch and reload the run: typed outputs, trace and review records survive.
6. Run synthetic evaluation and compare labels; do not claim field accuracy.

Visual inspection of your V0 screenshot proves only that the pictured form opened. It does not prove V1 execution, live Gemini calls or evaluation results. Capture the V1 screen after Analyze Incident for the next post.
