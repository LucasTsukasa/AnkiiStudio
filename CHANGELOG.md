# Changelog

Todas as alterações relevantes do BenkyouStudio são registradas neste arquivo.

O formato segue os princípios de [Keep a Changelog](https://keepachangelog.com/) e o projeto utiliza versionamento semântico durante o desenvolvimento.

## [0.11.0] - 2026-08-15

### Corrigido
- Ajustada a largura expandida da barra lateral para acomodar integralmente o novo nome **BenkyouStudio** no cabeçalho, sem corte do texto.
- O atualizador portátil agora cria um backup completo da instalação atual antes de remover qualquer arquivo da aplicação. Se a cópia da nova versão ou sua inicialização falhar, o updater restaura automaticamente a instalação anterior e tenta reabri-la, preservando `data/`.
- O carregamento de perfis Gemini TTS/ElevenLabs deixou de sobrescrever a configuração persistida quando o JSON salvo estiver inválido. Perfis válidos de uma coleção parcialmente inválida continuam utilizáveis, enquanto os itens inválidos são ignorados sem regravar o valor original.

### Alterado
- O aplicativo foi renomeado de **AnkiiStudio** para **BenkyouStudio** antes da primeira release estável. O pacote Python interno e identificadores legados necessários à compatibilidade permanecem preservados.
- Os `User-Agent` HTTP do BenkyouStudio passam a utilizar uma única constante derivada de `APP_VERSION`, eliminando strings de versão duplicadas em serviços de áudio, imagens, Roadmap, Wikimedia e atualização.
- Updater, Roadmap e links públicos do README agora apontam para o repositório oficial renomeado `LucasTsukasa/BenkyouStudio`.

### Distribuição
- Executável principal: `BenkyouStudio.exe`. O build 0.11.0 mantém um alias `AnkiiStudio.exe` apenas para permitir atualização in-place a partir da beta.9.
- Versão promovida de `0.11.0-beta.9` para `0.11.0` estável.
- Pacote portátil esperado: `BenkyouStudio-Portable-0.11.0.zip`.

## [0.11.0-beta.9] - 2026-08-14

### Corrigido
- A geração interna com Gemini agora valida os componentes de conteúdo selecionados na estrutura. Se Exemplo, Explicação, Mnemônico ou outro campo textual obrigatório vier vazio, a resposta é rejeitada e recebe uma nova tentativa automática em vez de criar silenciosamente um baralho incompleto.
- O structured output da Gemini agora utiliza um JSON Schema dinâmico: campos selecionados são marcados como obrigatórios e não vazios, e a quantidade fixa também é restringida no próprio schema antes da validação pós-resposta.
- O prompt destinado a IAs externas passou a exigir JSON estrito, escapes corretos para aspas/barras dentro de strings, ausência de vírgulas finais, Markdown, comentários ou texto externo, e também usa schema coerente com os componentes selecionados.
- A importação JSON/TXT agora normaliza de forma conservadora problemas comuns de conteúdo copiado de IAs: BOM, um único bloco Markdown JSON, texto simples antes/depois de um único objeto, vírgulas finais estruturais, delimitadores duplicados simples e aspas internas não escapadas reconhecíveis. Estruturas ambíguas continuam sendo rejeitadas e o erro mostra o trecho próximo da falha.
- Conteúdo colado e conteúdo carregado de arquivo passam explicitamente pelo mesmo pipeline de extração, reparo seguro e validação.
- Perfis Gemini TTS e ElevenLabs criados/editados/removidos em Configurações são atualizados no painel de áudio de um projeto já aberto sem recarregar o projeto ou descartar edições locais.
- Falhas de áudio por ausência de perfil compatível, perfil selecionado indisponível ou API key ausente agora informam a causa específica em vez de apenas exibir `provedor: indisponível`.
- A busca automática de imagens agora preserva `image_search_terms` quando Imagem faz parte da estrutura, tenta primeiro o conteúdo principal original e classifica os candidatos por relevância textual antes de baixar a imagem. Resultados que não atingem relevância suficiente são ignorados em vez de serem aceitos apenas por aparecerem primeiro na fonte.
- A pré-visualização Desktop em **Projetos → Estrutura e aparência** deixou de impor uma largura fixa ao layout externo. O preview mantém o limite de 760 px quando houver espaço, mas pode encolher dentro do viewport sem ultrapassar a janela; o modo Celular mantém seu limite próprio.
- Removidas referências e testes que exigiam a pasta `docs/`, cuja exclusão do repositório é intencional. A infraestrutura funcional do Design System e do gancho de assinatura permanece no código.

### Preservado
- Os reparos de JSON permanecem deliberadamente conservadores: o importador não converte sintaxes arbitrárias nem inventa valores quando a estrutura é ambígua.
- Funcionalidades não relacionadas às correções desta rodada permanecem na arquitetura funcional existente.

### Distribuição
- Versão atualizada para `0.11.0-beta.9`.

## [0.11.0-beta.8] - 2026-08-14

### Adicionado
- **AnkiiStudio Design System v1**, camada visual própria construída sobre Qt/PySide6 sem substituir o toolkit.
- Design tokens centralizados para temas, tipografia, espaçamento, raios, tamanhos de controles e breakpoints responsivos.
- `ThemeManager` para aplicar de forma coordenada `QPalette`, stylesheet, estilo proxy e tema ativo.
- `IconRegistry` central para resolução de ícones e estados ativo/inativo.
- Componentes reutilizáveis `ASButton`, `ASLineEdit`, `ASTextEdit`, `ASPlainTextEdit`, `ASComboBox`, `ASCard`, `ASDialog`, `ASTabWidget`, `ASContextMenu`, `ASToast`, `ASProgressBar`, `ASTableView`, `ASTableWidget`, `ASSidebar`, `ASSidebarItem`, `ASSwitch`, `ASPageHeader` e `ASSectionCard`.
- `AnkiiStudioProxyStyle` para métricas visuais centralizadas sem reimplementar comportamento nativo do Qt.
- Utilitários responsivos compartilhados, incluindo breakpoints Compacto/Médio/Amplo e cálculo de colunas para grids.

### Alterado
- Inicialização e troca de tema passam pelo novo Theme Manager, mantendo os temas Escuro, Claro e Carmesim.
- Cores dos temas passaram a ter uma fonte de verdade em `design_system/tokens.py`; o stylesheet histórico agora consome esses tokens.
- Botões, campos de texto, combos, cards, diálogos e tabelas das telas atuais foram migrados para componentes `AS*` quando compatível, preservando contratos e lógica existente.
- Configurações e Atualizações agora usam `ASDialog`; Projetos usa `ASTabWidget`, `ASContextMenu`, `ASLineEdit`, `ASComboBox` e cards do design system.
- A sidebar principal passou a usar `ASSidebar`/`ASSidebarItem` e o registro central de ícones.
- O gerenciador de tarefas usa o componente de progresso do design system e notificações independentes podem ser exibidas pelo novo sistema de toasts.
- Cabeçalhos e cards reutilizáveis existentes foram conectados à nova camada visual para permitir migração sem refatoração destrutiva.

### Complementos e correções de UI/UX da beta.8
- Corrigida a faixa intermediária de largura na tela **Criar** em que o layout permanecia no modo amplo mesmo sem espaço útil suficiente, causando corte do botão de exclusão de preset. O breakpoint agora considera o viewport real do scroll, as margens da página e o padding dos cards.
- `PageScrollArea` passa a informar alterações reais do viewport para que páginas responsivas reajam também a mudanças causadas por scrollbar, sidebar e redimensionamento da janela.
- O cálculo de colunas responsivas agora considera o espaçamento entre cards, evitando grades que escolhiam uma coluna a mais do que cabia confortavelmente.
- Home e biblioteca de Projetos passaram a usar a largura efetivamente disponível para reorganizar cards e filtros.
- O estado vazio de **Projetos recentes** ficou mais compacto e informativo, sem reservar uma grande área vazia quando ainda não existem projetos.
- A janela principal passa a respeitar a área útil do monitor, incluindo barra de tarefas e decorações da janela, reduzindo o tamanho inicial somente quando necessário.
- O tamanho e a posição da janela principal passam a ser restaurados entre execuções e são reajustados quando ficariam fora dos monitores atualmente conectados.
- O controle de recolhimento da sidebar recebeu chevrons simples, área clicável previsível, alinhamento apropriado e nome acessível.
- A página de Áudio passou a utilizar a mesma medição de viewport real para seu layout adaptativo.
- A pré-visualização em **Projetos → Estrutura e aparência** recebeu uma área de apresentação própria para Desktop/Celular, largura responsiva previsível e bloqueio do scroll horizontal que fazia o cartão parecer comprimido.
- A biblioteca de **Projetos** passou a usar tiles compactos de tamanho estável, alinhados à esquerda, em vez de esticar poucos projetos para preencher toda a linha.
- Os cards de projeto receberam menu de contexto visualmente mais discreto, pluralização correta de `cartão/cartões` e data de atualização apresentada no formato da interface em português.
- A tela **Criar** recebeu hierarquia de seções mais consistente, preset mais compacto e uma barra inferior persistente para manter as ações de criação acessíveis durante a rolagem.

### Otimizações de desempenho
- Implementado carregamento preguiçoso das páginas principais, reduzindo o trabalho executado durante a inicialização do aplicativo.
- Ferramentas mais pesadas da área de Projetos passam a ser construídas somente quando o usuário realmente abre o projeto correspondente.
- A pré-visualização de cartões passa a consultar apenas um cartão de amostra, evitando carregar todos os cartões do projeto apenas para renderizar o preview.
- Adicionado debounce na atualização da pré-visualização para evitar renderizações repetidas durante alterações rápidas de configuração.
- Contagens e listagens de seções passam a utilizar consultas agregadas diretamente no SQLite sempre que possível.
- A página inicial utiliza contagens agregadas de cartões em vez de carregar todos os cartões de cada projeto apenas para exibir totais.
- A pesquisa da biblioteca de Projetos passa a utilizar debounce para evitar reconstruções a cada caractere digitado.
- O redimensionamento da biblioteca de Projetos reposiciona os cards existentes quando a quantidade de colunas muda, evitando reconstruções desnecessárias da biblioteca.
- Atualizações de mídia relacionadas ao mesmo cartão passam a utilizar operações SQLite agrupadas em transações, reduzindo conexões e estados intermediários.
- Conexões HTTP passam a ser reutilizadas durante operações em lote de imagens e áudio, aproveitando connection pooling e keep-alive.
- O roteador e os provedores de áudio podem ser reutilizados durante a geração em lote, reduzindo reconstruções repetidas de serviços.
- Hashes de arquivos passam a ser calculados em streaming, evitando carregar arquivos inteiros na memória.
- A importação de áudio em lote evita consultas repetidas ao banco carregando os cartões necessários de forma agrupada.
- Etapas pesadas de importação e exportação passam a ser executadas fora da thread principal da interface quando aplicável, preservando a responsividade da janela.
- Validações repetitivas de artefatos de imagem utilizam cache enquanto caminho, tamanho e data de modificação do arquivo permanecerem inalterados.

### Preservado
- Nenhuma mudança foi feita na política de importação/recuperação de JSON/TXT ou no prompt de importação por causa de JSON malformado.
- Funcionalidades de criação, projetos, áudio, imagens, IA, exportação e persistência permanecem na arquitetura funcional existente.

### Distribuição
- Versão atualizada para `0.11.0-beta.8`.

## [0.11.0-beta.7] - 2026-08-13

### Adicionado
- Biblioteca visual de Projetos com pesquisa por nome/tema, filtro por idioma e ordenação por atividade recente, nome ou quantidade de cartões.
- Duplicação de projetos pelo menu `⋯` e pelo menu de contexto, preservando configurações, cartões e metadados de mídia.
- Presets de criação persistentes para reaplicar configurações de idioma, modelo, estrutura, áudio e mídia sem armazenar credenciais.
- Modo de quantidade **Automática** para geração por IA, permitindo que o Gemini determine uma contagem adequada dentro de um limite máximo de segurança.
- Barra lateral recolhível para modo somente ícones, com persistência do estado.
- Gerenciador visual de múltiplas tarefas para acompanhar imagem e áudio de forma independente.
- Ações globais de Desfazer/Refazer para editores de texto e carregamento das traduções nativas do Qt para menus de contexto.
- Janela própria de atualização com versão instalada, versão disponível, canal e notas da release.
- Janela categorizada de Configurações, inspirada em um layout de navegação lateral com conteúdo à direita.
- Painel de áudio específico por projeto e gerenciamento global de provedores/perfis dentro de Configurações.
- Pré-visualização de cartão com fluxo Frente → Mostrar resposta e modos de largura Desktop/Celular.
- Gancho opcional de assinatura Authenticode no build Windows.

### Alterado
- As funcionalidades da antiga página **Modelos** foram incorporadas a **Projetos → Estrutura e aparência**.
- As configurações globais da antiga página **Áudios** foram movidas para **Configurações → Áudio**, enquanto opções específicas continuam vinculadas ao projeto.
- A navegação principal foi simplificada para Início, Criar, Projetos, Roadmap, Configurações e Sobre.
- A tela Criar foi reorganizada em seções recolhíveis e passou a oferecer gerenciamento de presets e configuração de quantidade fixa/automática.
- A mensagem da página inicial agora apresenta o AnkiiStudio de forma mais ampla como ferramenta para transformar conteúdos em materiais de estudo, sem anunciar módulos ainda não implementados.
- Atualizações de imagem e áudio no banco passam a gravar somente os campos de mídia correspondentes.
- O estilo global de `QLabel` usa fundo transparente para eliminar o artefato visual de retângulo/sombra sob textos.

### Corrigido
- Busca/download de imagens e geração de áudios que compartilhavam a mesma área de progresso e podiam sobrescrever o status uma da outra.
- Concorrência entre workers de imagem e áudio que podia regravar um snapshot antigo do cartão e perder a mídia gravada pela outra tarefa.
- Associação do progresso de tarefas em lote ao projeto errado quando o usuário mudava de projeto durante o processamento.
- Menus de contexto de edição que permaneciam em Inglês quando a interface estava configurada para Português, quando as traduções Qt correspondentes estão disponíveis no runtime.

### Complementos e correções da beta.7
- Adicionado tema visual **Carmesim** para o aplicativo, baseado em `#1A1A1A` e `#A4133C`, sem substituir os temas Claro e Escuro.
- Adicionado **tema padrão global dos flashcards** em Configurações → Aparência. Novos projetos recebem uma cópia desse tema; projetos existentes permanecem independentes e podem aplicar o padrão manualmente em Estrutura e aparência.
- A criação de presets passa a preservar também o tema do cartão, preferências de voz por provedor e os ajustes de VOICEVOX (personagem/estilo, velocidade, tom, entonação, volume e pausas), sem armazenar chaves de API.
- Configurações → Áudio passa a permitir carregar, escolher, ajustar e ouvir a voz padrão do VOICEVOX, além de ouvir perfis Gemini TTS e ElevenLabs.
- Criar → Mídias e áudio ganhou uma seção **Avançado** com escolha e prévia de VOICEVOX, Gemini TTS e ElevenLabs, permitindo salvar essas preferências nos presets.
- Projetos → Áudio do projeto passa a permitir definir e ouvir uma voz preferida por provedor nos modos inteligente/aleatório.
- Corrigida a geração Gemini para idiomas diferentes de Japonês: a resposta da geração interna agora exige explicitamente `language` e `translation_language`, evitando fallback silencioso para `ja` quando o modelo omite esses campos.
- Corrigida a geração com quantidade fixa: o AnkiiStudio exige exatamente a quantidade solicitada, tenta uma correção automática uma vez e rejeita a criação incompleta caso a Gemini continue retornando menos/mais cartões.
- Corrigido o layout responsivo de Cartões dentro de Projetos em larguras reduzidas, evitando compressão/sobreposição da tabela, botões de seleção e editor.
- O comportamento do importador externo de JSON/TXT e o prompt de importação permanecem inalterados nesta rodada.

### Distribuição
- Versão atualizada para `0.11.0-beta.7`.
- O script de build tenta assinar `AnkiiStudio.exe` antes de empacotar quando as variáveis de assinatura estão configuradas; builds sem certificado continuam possíveis e são identificados como não assinados.

## [0.11.0-beta.6] - 2026-08-11

### Adicionado
- Nova página **Roadmap** em formato de linha do tempo vertical, com os estados `✓ CONCLUÍDO`, `◉ EM DESENVOLVIMENTO` e `◇ PLANEJADO`.
- Conteúdo do Roadmap separado em `ankiistudio/resources/roadmap.json`, permitindo manutenção por commits sem acoplar o planejamento ao código da interface.
- Atualização silenciosa do Roadmap a partir do repositório público quando houver internet, mantendo cópia local/cache como fallback offline.
- Personalização avançada do tema dos cartões: tamanhos independentes de Conteúdo principal, Leitura, Romanização, Tradução, Exemplo, Explicação e Mnemônico; altura máxima de imagem; largura máxima do cartão; espaçamento interno e espaço entre componentes.
- Presets de densidade visual **Compacto**, **Normal**, **Espaçoso** e **Personalizado**.
- **IA por campo** no editor de cartões para **Exemplo**, **Explicação** e **Mnemônico**, usando a chave/modelo Gemini configurados pelo próprio usuário.
- Ações de IA representadas apenas pelo ícone `✨`, com indicador animado durante o processamento e sem salvar automaticamente o resultado.

### Alterado
- O conteúdo editável do Roadmap deixou de ser traduzido pela interface: títulos, descrições e listas agora permanecem exatamente no idioma escrito em `roadmap.json`; somente elementos fixos da página e os status usam internacionalização.
- O estilo padrão dos cartões foi levemente compactado, reduzindo o espaço desperdiçado em telas menores do Anki sem remover conteúdo.
- O script de build portátil valida que `AnkiiStudio.exe` esteja na raiz do ZIP, mantendo compatibilidade com atualizadores de versões antigas.

### Corrigido
- O atualizador agora aceita tanto pacotes com `AnkiiStudio.exe` diretamente na raiz quanto pacotes com uma única pasta contêiner `AnkiiStudio/`, corrigindo a falha “O pacote de atualização não contém AnkiiStudio.exe na raiz.”.

## [0.11.0-beta.5] - 2026-08-10

### Corrigido
- Busca automática/em lote de imagens para cartões sem `image_search_terms` agora pesquisa primeiro o Conteúdo principal original do cartão. Kana como `お` é consultado como `お`, em vez de usar primeiro a tradução latina `O`.
- A tradução permanece disponível apenas como fallback quando a busca pelo conteúdo original não encontra uma imagem utilizável.
- Cartões que possuem `image_search_terms` explícitos preservam a prioridade desses termos visuais, mantendo o comportamento já aprovado para palavras e conceitos com consultas auxiliares específicas.

## [0.11.0-beta.4] - 2026-08-10

### Adicionado
- Filtro de fontes na pesquisa manual de imagens, acessível pelo ícone ao lado do campo de busca e limitado às fontes habilitadas nas Configurações.
- Pacotes de idioma separados em `ankiistudio/languages/`, inicialmente para Português (Brasil) e Inglês.

### Alterado
- Troca do idioma da interface passa a ocorrer imediatamente pelas Configurações, sem necessidade de reiniciar o AnkiiStudio.
- Janela **Pesquisar imagem** recebeu novo layout com resultados em miniaturas, pré-visualização mais compacta, metadados organizados e sugestões auxiliares em blocos menores.
- Pixabay e Pexels permanecem como fontes opcionais, enquanto Wikimedia Commons continua habilitado por padrão.

### Removido
- Integração com Openverse, incluindo configuração, fonte de pesquisa, lógica de consulta e interface associada.

## [0.11.0-beta.3] - 2026-08-10

### Adicionado
- Interface em Inglês, com Português (Brasil) mantido como idioma padrão e seleção persistente em Configurações.
- Campo **Idioma da tradução** na criação de projetos, independente do idioma da interface e do idioma estudado.
- Localização em Inglês dos campos destinados ao estudante no conteúdo interno revisado disponível nesta versão.
- Buscas auxiliares na pesquisa manual de imagem de um único cartão, utilizando tradução, romanização, leitura e termos visuais disponíveis.

### Alterado
- A pesquisa manual de imagem usa sempre o conteúdo principal original do cartão como consulta principal; termos auxiliares não substituem essa consulta.
- A pré-visualização da imagem selecionada foi reduzida para abrir espaço às sugestões auxiliares, separadas por um divisor visual neutro.
- Falhas individuais das fontes de imagem passam a ficar visíveis na pesquisa manual em vez de serem ocultadas quando outra fonte retorna resultados.
- Projetos persistem o idioma da tradução; projetos antigos recebem Português como valor compatível de migração.

### Corrigido
- Encerramento do aplicativo durante pesquisas manuais de imagem causado por callbacks assíncronos que podiam alcançar a interface fora do ciclo seguro da thread Qt.
- Busca manual de kana como `あ` sendo substituída pela tradução `A` antes da consulta.

## [0.11.0-beta.2] - 2026-08-10

### Adicionado
- Verificação opcional de atualizações publicadas no GitHub, com busca automática configurável, verificação manual e fluxo de download/atualização da distribuição portátil para Windows.
- Pixabay e Pexels como fontes opcionais de imagens; Wikimedia Commons permanece habilitado por padrão.
- Configuração segura das API keys de Pixabay e Pexels pelo gerenciador de credenciais do sistema.
- Importação manual e remoção de imagem no cartão selecionado.
- Remoção do áudio associado ao cartão selecionado.
- Edição de vários cartões com alterações pendentes em memória e salvamento conjunto.
- Aviso de alterações não salvas antes de fechar, trocar de projeto, exportar ou executar operações que dependem dos dados persistidos.
- Exclusão de múltiplos cartões selecionados em uma única ação.

### Alterado
- Busca de imagens passa a priorizar termos visuais explícitos e, na ausência deles, a tradução antes do conteúdo original.
- O prompt de geração de cartões volta a solicitar termos concretos de busca de imagem quando o cartão utiliza imagem.
- Resultados de várias fontes de imagem são combinados sem permitir que uma única biblioteca monopolize a primeira lista apresentada ao usuário.
- Consultas do Pixabay são mantidas em cache persistente por 24 horas.

### Corrigido
- Seleção automática de imagens semanticamente inadequadas em consultas não latinas, incluindo casos em que um termo japonês podia resultar em uma fotografia sem relação clara com o significado do cartão.
- Fluxo de edição que exigia salvar cada cartão individualmente antes de avançar para o próximo.
- Exclusão limitada a um único cartão mesmo quando várias linhas estavam selecionadas.

## [0.11.0-beta.1] - 2026-08-10

### Adicionado
- Integração com o Tatoeba para buscar gravações humanas por correspondência exata do conteúdo, preservando metadados de origem, autoria e licença.
- Importação manual de um arquivo de áudio para o cartão selecionado.
- Importação de áudios em lote por nome de arquivo, com correspondência por Conteúdo principal, Leitura, Romaji/Romanização ou Tradução.
- Pré-visualização da importação em lote, com identificação de correspondências, conflitos, casos ambíguos e arquivos sem cartão correspondente.
- Suporte a múltiplas variações de estrutura em um mesmo projeto.
- Distribuição aleatória equilibrada dos cartões entre as variações configuradas.

### Alterado
- Geração e validação de mídias passam a respeitar a variação de estrutura atribuída a cada cartão.
- Exportação `.apkg` cria o modelo de nota correspondente à variação de cada cartão.
- O README foi atualizado para apresentar as novas fontes de áudio, importação em lote e variações de estrutura sem vincular a apresentação do projeto a um idioma específico.

### Compatibilidade
- Projetos antigos sem variações continuam utilizando a estrutura única já salva.
- Campos de estrutura e áudio legados continuam reconhecidos para abertura de projetos anteriores.

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
