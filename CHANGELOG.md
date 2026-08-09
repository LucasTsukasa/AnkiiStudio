# Changelog

Todas as alterações relevantes do AnkiiStudio são registradas neste arquivo.

O formato segue os princípios de [Keep a Changelog](https://keepachangelog.com/) e o projeto utiliza versionamento semântico durante o desenvolvimento.

## [0.10.0] - 2026-08-09

### Alterado
- O seletor pesquisável compartilhado agora usa `QCompleter` em modo não filtrado, mantendo o foco no campo de texto enquanto a lista de sugestões permanece aberta.
- A seleção de personagem/estilo do VOICEVOX reage ao mesmo evento de mudança usado pelos demais seletores pesquisáveis.
- Thumbnails rasterizadas de SVGs do Wikimedia são compostas explicitamente sobre fundo branco antes da conversão para WebP.
- O cache de imagem diferencia processamento com transparência preservada e transparência achatada.

### Corrigido
- Campo de Modelo/Idioma/VOICEVOX que abria a lista, mas impedia a digitação depois do clique.
- Imagens de kana/kanji vindas de SVG do Wikimedia que podiam virar um retângulo preto no Anki por depender apenas do canal alfa.
- Imagens antigas com o padrão RGB totalmente preto + alpha variável passam a ser reconhecidas como artefato e podem ser regeneradas em lote.

## [0.9.0] - 2026-08-09

### Adicionado
- Catálogo pesquisável com 184 idiomas ISO 639-1.
- Suporte a códigos ISO/BCP-47 nos modelos de projeto e perfis de voz.
- Persistência do nome amigável do personagem/estilo selecionado no VOICEVOX.
- Suporte a imagens SVG do Wikimedia Commons usando a miniatura rasterizada pelo próprio Commons.

### Alterado
- Seletor pesquisável refeito: clique em qualquer região abre a lista e a digitação reorganiza resultados sem ocultá-los.
- Aba Áudios entra no modo compacto em uma largura maior para evitar compressão dos cards.
- Miniaturas do Wikimedia para imagens vetoriais são solicitadas em 900 px.
- `eleven_multilingual_v2` usa normalização geral automática sem enviar combinação incompatível de normalização de idioma.

### Corrigido
- Pesquisa de Idioma que podia retornar temporariamente ao Japonês durante a digitação.
- Pesquisa do VOICEVOX que podia bloquear a edição do texto.
- Fluxo de seleção/salvamento do personagem/estilo do VOICEVOX.
- Erro ElevenLabs 400: `Language text normalization is not supported for language code 'None'`.
- SVGs relevantes do Wikimedia que eram descartados e faziam o aplicativo escolher imagens rasterizadas piores.

## [0.8.0] - 2026-08-09

### Adicionado
- Pesquisa por relevância nos seletores de Modelo, Idioma e personagem/estilo do VOICEVOX, mantendo todos os resultados visíveis.
- Ajustes por perfil ElevenLabs para estabilidade, similaridade, estilo, velocidade e Speaker Boost.
- Ajustes de velocidade, tom, entonação, volume e pausas para VOICEVOX.
- Reprodução do exemplo do VOICEVOX diretamente no AnkiiStudio.
- Armazenamento portátil em `data/` ao lado do aplicativo para banco, mídias, cache, exports e logs.
- Diagnóstico detalhado de respostas de erro da ElevenLabs.

### Alterado
- Estrutura visual simplificada para Imagem, Conteúdo principal, Leitura, Romaji/Romanização, Tradução, Áudio, Exemplo, Explicação e Mnemônico.
- Os componentes antigos de áudio foram unificados em um único componente `Áudio`, que sempre sintetiza o conteúdo principal.
- Busca automática de imagem usa primeiro o conteúdo original e somente depois a tradução.
- Aba Áudios entra no layout compacto mais cedo para evitar compressão em janelas portáteis.
- Chaves de API continuam no gerenciador de credenciais do sistema; `.env.example` foi removido.
- Distribuição passa a ser somente portátil nesta fase; script de instalador foi removido.
- Novos arquivos `app.png` e `app.ico` fornecidos para a identidade do aplicativo.

### Corrigido
- Geração de exemplos/frases artificiais causada apenas pela presença de áudio na estrutura.
- Associação semântica indevida de kana a termos de imagem gerados pela IA.
- Traduções descritivas de kana na base padrão, como “som a”, substituídas por valores diretos, como `A`.
- Repetição da mesma requisição ElevenLabs inválida para todos os cartões de um lote após erro permanente.
- Perda da mensagem real retornada pela ElevenLabs em respostas HTTP 400/422.
- Persistência e migração de ajustes do VOICEVOX.
- Mensagem pós-exportação esclarece o limite diário de cartões novos do Anki quando o pacote contém mais cartões do que a tela de estudo exibe.

## [0.7.0] - 2026-08-08

### Adicionado
- Pesquisa diretamente na caixa de seleção de modelos.
- Perfis ilimitados de voz por idioma para Gemini TTS.
- Perfis ilimitados de voz por idioma para ElevenLabs.
- Seleção de personagem/estilo do VOICEVOX a partir de `/speakers`.
- Reprodução de exemplo para a voz selecionada do VOICEVOX.
- Aviso de mídias ausentes antes da exportação, com opção de continuar quando o cartão permanece válido.

### Alterado
- Aparência das telas Criar, Áudios, Configurações e Projetos restaurada para a composição visual da 0.5.0, mantendo responsividade.
- Modelos padrão agora bloqueiam Tema/contexto, Quantidade e métodos alternativos de criação; `Conteúdo padrão` é utilizado automaticamente.
- Gemini e ElevenLabs deixam de usar os slots globais `Natural A/B` e passam a utilizar perfis de voz.
- A disponibilidade do ElevenLabs considera API key e perfil de voz compatível com o idioma do projeto.
- VOICEVOX deixa de exigir Speaker ID manual na interface.
- A síntese do VOICEVOX preserva os parâmetros retornados pelo engine.

### Corrigido
- Layout responsivo sem substituir a identidade visual aprovada da 0.5.0.
- Estado incorreto de ElevenLabs como configurado quando não havia Voice ID utilizável.
- Exportação bloqueada desnecessariamente por áudio ou imagem ausente em cartões que ainda possuíam frente válida.
- Fluxo fixo de áudio para selecionar um perfil exato de Gemini/ElevenLabs.

## [0.6.0] - 2026-08-08

### Adicionado
- Idiomas Inglês, Espanhol e Coreano, inicialmente com o modelo Personalizado.
- Nova identidade visual e nova logo do AnkiiStudio.
- Base padrão revisada de Hiragana, Katakana e Frases Básicas.
- Estrutura inicial automática para cada modelo padrão.
- Arquivos de publicação no GitHub: `LICENSE`, `CHANGELOG.md`, `.gitignore` e `.env.example`.
- Licença GPL-3.0.

### Alterado
- Modelo Personalizado passa a ser a opção inicial da tela Criar.
- Modelos padrão antigos foram removidos; permanecem Hiragana, Katakana e Frases Básicas para japonês.
- Interface Criar reorganizada para largura compacta, com campos e estrutura empilhados.
- Interface Áudios reorganizada para largura compacta, com provedores em blocos verticais.
- Tela Projetos usa layout adaptativo e reserva mais espaço para a tabela de cartões.
- Modelos e pré-visualização passam a se adaptar melhor à largura disponível.
- Textos explicativos revisados para linguagem mais objetiva e profissional.
- Prompt de IA adaptado ao idioma selecionado.
- API keys permanecem configuráveis diretamente no aplicativo.

### Corrigido
- Cortes de campos e controles nas telas Criar e Áudios em janelas medianas.
- Área excessivamente pequena da lista de cartões em Projetos.
- Empacotamento dos novos recursos PNG e da base JSON de conteúdo padrão.

## [0.5.0] - 2026-08-07

### Adicionado
- Progresso de geração de imagens e áudios em massa.
- Status de uso observado dos modelos Gemini TTS.
- Pré-visualização baseada no renderer dos cartões exportados.
- Exportação com destino inicial em Downloads.

### Alterado
- Organização da aba Áudios por provedores e modelos.
- Mensagens de limite da Gemini tornadas mais legíveis.

## [0.4.0] - 2026-08-07

### Adicionado
- Geração de imagens e áudios para todos os cartões.
- Seleção de cartões para exportação.
- Subbaralhos e edição de estrutura do projeto.
- Tema claro e configuração visual por baralho.

### Corrigido
- Identidade única de notas na exportação.
- Validação de arquivos de mídia antes da criação do `.apkg`.
- Tratamento de falhas do VOICEVOX.

## [0.3.0] - 2026-08-07

### Adicionado
- Modelo Personalizado.
- Conteúdos personalizados separados de tema/contexto.
- Prompt estruturado aprimorado.

### Corrigido
- Importação tolerante ao caso conhecido de aspas internas não escapadas em JSON produzido por IA.
- Mensagens de erro do VOICEVOX.

## [0.2.0] - 2026-08-07

### Alterado
- Reformulação inicial da interface e navegação com ícones.

## [0.1.0] - 2026-08-07

### Adicionado
- Primeira versão funcional do AnkiiStudio.
- Projetos, cartões, integração inicial com IA, mídias e exportação `.apkg`.
