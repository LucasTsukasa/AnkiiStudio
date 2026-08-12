# Relatório de execução — AnkiiStudio 0.11.0-beta.6

Data: 2026-08-11

## Escopo executado

### Atualizador portátil

- Corrigido o reconhecimento de pacotes que possuem uma única pasta contêiner `AnkiiStudio/` antes de `AnkiiStudio.exe`.
- Mantido suporte ao formato tradicional com `AnkiiStudio.exe` diretamente na raiz.
- Estruturas ambíguas continuam sendo rejeitadas.
- O script de build passa a validar explicitamente que o ZIP gerado contém `AnkiiStudio.exe` na raiz, mantendo compatibilidade com atualizadores antigos.

### Personalização dos cartões

- Adicionados tamanhos independentes para Conteúdo principal, Leitura, Romanização, Tradução, Exemplo, Explicação e Mnemônico.
- Adicionados controles para altura máxima da imagem, largura máxima do cartão, espaçamento interno e espaço entre componentes.
- Adicionados presets de densidade: Compacto, Normal, Espaçoso e Personalizado.
- O preset Normal passa a usar um layout um pouco mais compacto que o estilo anterior, principalmente na altura máxima de imagens e espaçamentos.
- A pré-visualização continua usando o mesmo renderer/CSS da exportação.

### Roadmap

- Adicionada página Roadmap na sidebar, antes de Sobre.
- Timeline vertical responsiva com cards alternados em larguras maiores e layout linear em larguras menores.
- Status públicos: `✓ CONCLUÍDO`, `◉ EM DESENVOLVIMENTO`, `◇ PLANEJADO`.
- Conteúdo armazenado em `ankiistudio/resources/roadmap.json`, separado da UI.
- Atualização remota silenciosa pelo arquivo público no GitHub, com cache local e fallback para o arquivo distribuído.
- O conteúdo editável do Roadmap permanece exatamente como escrito no JSON e não é traduzido pela interface.
- Somente textos fixos da página e os status `✓ CONCLUÍDO`, `◉ EM DESENVOLVIMENTO` e `◇ PLANEJADO` continuam no sistema de internacionalização.

### IA por campo

- Adicionada IA por campo exclusivamente para **Exemplo**, **Explicação** e **Mnemônico** no editor de cartões.
- Cada campo compatível possui somente o botão discreto `✨`; durante a chamada, o botão mostra um spinner animado.
- A função reutiliza a chave e o modelo de texto Gemini já configurados pelo usuário.
- Nenhuma requisição é feita automaticamente: a Gemini só é chamada quando o usuário pressiona `✨`.
- O resultado entra como alteração pendente e só é persistido quando o usuário salva.
- Para o componente Exemplo, leitura/tradução auxiliares internas do próprio exemplo são atualizadas junto da nova frase para evitar conteúdo inconsistente; nenhum outro componente do cartão é alterado.
- Se o usuário alterar o mesmo campo enquanto a requisição estiver em processamento, a resposta é descartada para preservar a edição local mais recente.

## Itens deliberadamente não implementados

Permanecem apenas no planejamento futuro:

- criação a partir de PDF/PPTX/DOCX/TXT;
- Cloze;
- Dicionário integrado.

Não foram adicionados por decisão do usuário:

- Tags;
- edição em massa avançada;
- Image Occlusion.
