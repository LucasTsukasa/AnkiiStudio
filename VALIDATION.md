# Validação — AnkiiStudio 0.11.0-beta.6

Data: 2026-08-11

## Resultado automatizado

- `python -m compileall -q ankiistudio tests`: concluído sem erros.
- `python -m pytest -q -rs`: **192 passed, 1 skipped**.
- JSON de `roadmap.json`, `pt_BR.json` e `en_US.json`: carregados com sucesso.
- Estrutura real do pacote `AnkiiStudio-Portable-0.11.0-beta.5.zip` fornecido pelo usuário foi extraída e validada contra o novo resolvedor do atualizador: o payload `AnkiiStudio/AnkiiStudio.exe` foi reconhecido corretamente.

## Teste ignorado

- `tests/test_anki_export.py`: ignorado porque `genanki` não está instalado no ambiente de validação atual.

## Verificações específicas desta versão

- Atualizador aceita `AnkiiStudio.exe` na raiz do staging.
- Atualizador aceita uma única pasta contêiner contendo `AnkiiStudio.exe`.
- Atualizador rejeita estruturas ambíguas.
- CSS exportado respeita os novos tamanhos e dimensões do tema do cartão.
- Persistência do tema avançado foi coberta por round-trip no SQLite.
- Roadmap local e cache foram cobertos por testes do serviço.
- O schema do Roadmap foi validado sem conteúdo localizado: títulos, descrições e detalhes permanecem como texto livre único, independente do idioma da interface.
- A IA por campo foi coberta por testes com cliente Gemini simulado para Exemplo, Explicação e Mnemônico, incluindo validação de escopo e resposta estruturada.
- A interface da IA por campo foi verificada por contrato estático: somente os três campos aprovados recebem `✨`, com spinner animado e reutilização da chave Gemini existente.
- Build spec inclui `ankiistudio/resources/roadmap.json`.
- Script de build Windows valida a presença de `AnkiiStudio.exe` na raiz do ZIP portátil.

## Limitações do ambiente

Não foi possível validar neste ambiente:

- renderização visual real da interface PySide6, pois PySide6 não está instalado no runtime de validação;
- geração do executável Windows/PyInstaller;
- atualização real sobre uma instalação portátil Windows em execução;
- consulta online real do Roadmap no GitHub após publicação do novo `roadmap.json` no repositório;
- chamada real da Gemini API para IA por campo, pois nenhuma credencial de usuário foi utilizada no ambiente de validação;
- exportação `.apkg` real, devido à ausência de `genanki` neste ambiente.

O comando `python -m ruff check .` também não pôde ser executado porque `ruff` não está instalado no ambiente atual.
