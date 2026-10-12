# Practice in Cursor — Raquel Cruz

Use this working application as a learning project. Review diffs and run tests after each focused change. Explanations can be in Portuguese while the GUI remains in English.

## 1. Understand the existing flow

> Leia README.md, firewatch/models.py e firewatch/pipeline.py. Explique em português como um incidente vira avaliação, proposta, revisão e relatório. Identifique quais componentes realmente chamam o Gemini e quais são determinísticos. Não altere código nesta etapa.

## 2. Run and inspect

> Ajude-me a executar este projeto no Windows com os comandos do README, sem mudar a política do PowerShell. Explique o resultado dos testes e o que ainda preciso verificar na interface. Não afirme que houve validação visual se você não viu a execução.

## 3. Make a small GUI improvement

> Adicione um filtro ao histórico por local, preservando snapshots e regras de segurança. Explique os arquivos alterados e como verificar o comportamento. Faça somente esta melhoria.

## 4. Add one scenario

> Adicione um cenário sintético com chamas relatadas, exposição ausente e observação antiga. Antes de executar, escreva os rótulos esperados com base nas regras existentes. Execute os testes e a avaliação. Não apresente concordância sintética como precisão real.

## 5. Move the orchestrator to LangGraph later

> Proponha uma migração do coordenador para LangGraph usando a documentação oficial atual. Preserve os modelos, estados desconhecidos, route selection, limite de uma revisão, fallback e Safety Gate. Primeiro apresente o mapeamento dos nós e critérios de equivalência; implemente em mudanças pequenas.

## 6. Add multi-record evidence editing later

> A GUI atualmente cria uma evidência por análise. Adicione um editor de múltiplas evidências com origem, horário, provenance e IDs, mantendo o backend existente. Explique como evitar que campos normalizados e registros contraditórios sejam apresentados como fatos verificados.

Keep credentials out of prompts, source files, screenshots and commits. Cursor project rules are already in `.cursor/rules/project.mdc`.
