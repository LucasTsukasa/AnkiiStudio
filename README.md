<p align="center">
  <img src="ankiistudio/resources/icons/app.png" alt="AnkiiStudio" width="150">
</p>

<h1 align="center">AnkiiStudio</h1>

<p align="center">
  Crie, organize e exporte flashcards para o Anki com conteúdo estruturado, imagens e áudio.
</p>

<p align="center">
  <a href="https://github.com/LucasTsukasa/AnkiiStudio/releases">
    <img alt="Latest Release" src="https://img.shields.io/github/v/release/LucasTsukasa/AnkiiStudio?display_name=tag&sort=semver">
  </a>
  <img alt="Python" src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white">
  <img alt="Windows" src="https://img.shields.io/badge/Windows-Portable-0078D4?logo=windows&logoColor=white">
  <a href="LICENSE">
    <img alt="License" src="https://img.shields.io/badge/License-GPL--3.0-blue">
  </a>
</p>

<p align="center">
  <a href="https://github.com/LucasTsukasa/AnkiiStudio/releases"><strong>Download</strong></a>
  ·
  <a href="CHANGELOG.md">Changelog</a>
  ·
  <a href="https://github.com/LucasTsukasa/AnkiiStudio/issues">Issues</a>
  ·
  <a href="LICENSE">Licença</a>
</p>

---

## Sobre

**AnkiiStudio** é um aplicativo desktop para criação, organização e exportação de flashcards para o [Anki](https://apps.ankiweb.net/).

O projeto reúne em uma única interface as principais etapas de criação de um baralho: definição da estrutura dos cartões, geração ou importação de conteúdo, obtenção de imagens, geração de áudio, revisão e exportação.

Os projetos são exportados diretamente em `.apkg`, sem depender do AnkiConnect.

## Principais recursos

- Criação e gerenciamento de projetos de flashcards.
- Estrutura configurável de frente e verso.
- Múltiplas variações de estrutura no mesmo projeto, distribuídas de forma aleatória e equilibrada.
- Exportação direta para `.apkg`.
- Organização em baralhos e subbaralhos.
- Suporte a múltiplos idiomas.
- Interface disponível em Português (Brasil) e Inglês.
- Idioma de tradução configurável de forma independente por projeto.
- Modelos de flashcards prontos para idiomas compatíveis.
- Modelo personalizado para criação de estruturas próprias.
- Geração de conteúdo com Google Gemini.
- Importação de conteúdo estruturado por JSON/TXT.
- Busca e processamento de imagens com Wikimedia Commons por padrão e fontes adicionais opcionais.
- Áudio por Tatoeba, Wikimedia Commons, VOICEVOX, Gemini TTS e ElevenLabs.
- Importação individual e em lote de arquivos de áudio próprios.
- Importação e remoção manual de imagens e áudios por cartão.
- Edição de vários cartões com salvamento conjunto de alterações pendentes.
- Exclusão simultânea de múltiplos cartões selecionados.
- Verificação opcional de novas versões publicadas no GitHub.
- Perfis de voz configuráveis por idioma.
- Ajustes de voz por provedor.
- Reprodução de áudio dentro do aplicativo.
- Tema claro e escuro.
- Personalização avançada da aparência dos cartões, incluindo tamanhos, imagem, espaçamento e densidade de layout.
- Roadmap integrado em linha do tempo, com planejamento carregado de arquivo separado e atualização pública pelo GitHub.
- Armazenamento seguro de credenciais pelo sistema operacional.
- Distribuição portátil para Windows.

## Fluxo de criação

```text
Criar projeto
      ↓
Selecionar idioma e modelo
      ↓
Definir a estrutura dos cartões
      ↓
Criar ou importar conteúdo
      ↓
Adicionar imagens e áudio
      ↓
Revisar
      ↓
Exportar para .apkg
      ↓
Importar no Anki
```

## Idiomas e modelos

O AnkiiStudio foi desenvolvido para trabalhar com um amplo catálogo de idiomas.

Dependendo do idioma selecionado, o aplicativo pode disponibilizar **modelos de flashcards prontos**, com estrutura e conteúdo previamente definidos para determinados objetivos de estudo.

Além dos modelos disponíveis, o modo **Personalizado** permite criar baralhos adaptados a diferentes necessidades, definindo elementos como:

- conteúdo;
- tema ou contexto;
- quantidade de cartões;
- estrutura da frente;
- estrutura do verso;
- método de criação.

A disponibilidade de modelos prontos pode evoluir conforme novos conteúdos forem adicionados ao projeto.

### Idioma da interface e idioma da tradução

O idioma da interface é uma preferência global e atualmente pode ser definido como **Português (Brasil)** ou **English**. A alteração é aplicada imediatamente, sem reiniciar o aplicativo, e permanece salva para as próximas execuções.

Cada projeto também possui um **Idioma da tradução** independente do idioma estudado e do idioma da interface. Esse idioma orienta os campos destinados ao estudante, como tradução, explicação, mnemônico e tradução de exemplos quando o conteúdo é gerado ou importado. Projetos existentes mantêm a configuração já salva mesmo que o idioma da interface seja alterado.

O catálogo de idiomas de tradução acompanha o catálogo multilíngue do aplicativo. O conteúdo interno revisado incluído com o programa possui localização própria em Português e Inglês nesta versão; outros idiomas podem ser utilizados nos fluxos Personalizado com geração ou importação de conteúdo.

## Estrutura dos flashcards

Os cartões podem ser compostos por diferentes componentes:

- Imagem
- Conteúdo principal
- Leitura
- Romaji / Romanização
- Tradução
- Áudio
- Exemplo
- Explicação
- Mnemônico

A estrutura disponível pode variar conforme o modelo utilizado e pode ser personalizada quando o modelo permitir.

### Personalização visual

Em **Modelos → Tema do baralho**, cada projeto pode ajustar a aparência dos cartões exportados. Além das cores e da fonte, é possível configurar:

- tamanho do Conteúdo principal;
- tamanho da Leitura;
- tamanho da Romanização;
- tamanho da Tradução;
- tamanho do Exemplo;
- tamanho da Explicação;
- tamanho do Mnemônico;
- altura máxima da imagem;
- largura máxima do cartão;
- espaçamento interno;
- espaço entre componentes.

Os presets **Compacto**, **Normal** e **Espaçoso** aplicam combinações prontas de dimensões. Ao modificar manualmente os controles de layout, o projeto passa para o modo **Personalizado**.

### Variações de estrutura

Um mesmo projeto pode conter mais de uma variação de cartão. Cada variação possui sua própria composição de frente e verso.

Quando duas ou mais variações são configuradas, o AnkiiStudio distribui os conteúdos de forma **aleatória e equilibrada** entre elas. Isso permite combinar diferentes formas de estudo — por exemplo, reconhecimento, compreensão auditiva, produção e associação visual — dentro do mesmo baralho, sem duplicar automaticamente todos os conteúdos.

## Criação de conteúdo

O AnkiiStudio oferece diferentes formas de adicionar conteúdo aos projetos.

### Conteúdo com IA

A integração com **Google Gemini** permite gerar conteúdo estruturado de acordo com o idioma, modelo e configuração definidos no projeto.

Na página **Projetos**, os campos **Exemplo**, **Explicação** e **Mnemônico** também possuem uma ação discreta `✨` para gerar ou regenerar somente aquele componente com IA. A chamada acontece apenas quando o usuário aciona o botão, reutiliza a chave/modelo Gemini configurados e deixa o resultado como alteração pendente para revisão antes de salvar.

### Importação

Também é possível importar conteúdo previamente preparado em formatos estruturados, permitindo utilizar respostas geradas externamente ou materiais próprios.

### Conteúdo interno

Alguns modelos podem utilizar conteúdo fornecido diretamente pelo AnkiiStudio, sem necessidade de geração por IA.

## Imagens

O **Wikimedia Commons** permanece como a fonte de imagens habilitada por padrão. Em **Configurações**, o usuário pode ativar fontes adicionais quando quiser ampliar os resultados da busca:

- Pixabay
- Pexels

Pixabay e Pexels utilizam as API keys configuradas pelo próprio usuário. As fontes adicionais permanecem desabilitadas até serem ativadas manualmente.

Na pesquisa manual, um filtro ao lado do campo de busca permite restringir temporariamente a consulta às fontes que já estão habilitadas nas Configurações. Fontes desativadas continuam visíveis no filtro, mas não podem ser selecionadas até serem habilitadas globalmente.

O aplicativo pesquisa, seleciona, baixa e otimiza as mídias antes de vinculá-las aos cartões. Na busca automática/em lote, termos visuais explícitos (`image_search_terms`) continuam tendo prioridade quando existem. Quando o cartão não possui esses termos, o **Conteúdo principal original** é pesquisado primeiro e a tradução é usada apenas como fallback. Assim, caracteres como `お` são consultados como `お`, em vez de começar pela tradução latina `O`. O AnkiiStudio também reduz a aceitação de resultados do Wikimedia sem relação clara com consultas não latinas.

Na pesquisa manual de um único cartão, o **conteúdo principal original** é mantido como consulta principal. Tradução, leitura, romanização e termos visuais disponíveis no cartão aparecem como buscas auxiliares em miniaturas menores, permitindo comparar alternativas sem substituir o termo original. A janela apresenta os resultados em miniaturas visuais, com pré-visualização compacta, metadados organizados e sugestões auxiliares em seções menores.

Também é possível **importar uma imagem local** diretamente para um cartão ou **remover a imagem associada**. Quando disponíveis, informações de origem, autoria e licença das imagens obtidas por fontes externas são preservadas internamente.

## Áudio

O AnkiiStudio pode utilizar gravações humanas, síntese de voz e arquivos fornecidos pelo próprio usuário.

### Tatoeba

O AnkiiStudio pode procurar uma gravação humana correspondente ao conteúdo do cartão no Tatoeba. Quando uma correspondência reutilizável está disponível, a gravação pode ser associada ao cartão com os metadados de origem, autoria e licença preservados.

### Wikimedia Commons

Permite utilizar gravações disponíveis no Wikimedia quando houver mídia compatível com o conteúdo do cartão.

### VOICEVOX

Integração com o engine local do VOICEVOX.

O aplicativo permite consultar personagens e estilos disponíveis no engine, selecionar vozes e ajustar parâmetros de síntese.

### Gemini TTS

Permite configurar perfis de voz utilizando modelos e vozes compatíveis com o Google Gemini.

### ElevenLabs

Permite cadastrar perfis utilizando modelos e Voice IDs disponíveis para a conta configurada.

Os perfis podem incluir ajustes como:

- estabilidade;
- similaridade;
- estilo;
- velocidade;
- Speaker Boost.

> A disponibilidade de modelos, vozes, cotas e recursos depende dos serviços externos e do plano utilizado em cada plataforma.

### Importar áudio

Arquivos locais podem ser associados diretamente aos cartões, sem depender de serviços externos.

A importação em lote permite selecionar vários arquivos ou uma pasta e relacionar cada áudio ao cartão pelo nome do arquivo. O campo usado para a correspondência pode ser escolhido pelo usuário, incluindo conteúdo principal, leitura, romanização ou tradução.

Exemplo:

```text
あ.wav  →  cartão com conteúdo “あ”
い.wav  →  cartão com conteúdo “い”
う.wav  →  cartão com conteúdo “う”
```

Antes da aplicação, o AnkiiStudio apresenta as correspondências encontradas e identifica arquivos sem cartão correspondente, casos ambíguos e cartões que já possuem áudio.

## Edição de cartões

Alterações feitas em cartões podem permanecer pendentes enquanto o usuário navega entre diferentes itens do mesmo projeto. O botão **Salvar alterações** grava todas as modificações pendentes em conjunto.

Ao tentar fechar o aplicativo, trocar de projeto, exportar ou executar uma operação que dependa dos dados persistidos, o AnkiiStudio avisa quando existem alterações não salvas e permite salvar, continuar sem salvar ou cancelar a ação.

A tabela de cartões também suporta seleção múltipla para exclusão de vários cartões em uma única confirmação.

## Exportação para o Anki

Os projetos são exportados no formato:

```text
.apkg
```

O arquivo pode ser importado diretamente pelo Anki.

Também é possível organizar o conteúdo em subbaralhos utilizando a estrutura:

```text
Baralho::Subbaralho
```

Quando uma mídia opcional estiver ausente, a exportação ainda pode ser realizada se o cartão continuar contendo informações suficientes para estudo.

## Download

A versão portátil para Windows está disponível na página de:

**[GitHub Releases](https://github.com/LucasTsukasa/AnkiiStudio/releases)**

### Como executar

1. Baixe o arquivo `.zip` da versão desejada.
2. Extraia todo o conteúdo.
3. Execute `AnkiiStudio.exe`.

Estrutura típica da distribuição:

```text
AnkiiStudio/
├── AnkiiStudio.exe
├── _internal/
└── data/
```

> A pasta `_internal` contém dependências necessárias para execução e deve permanecer junto do aplicativo.

A versão portátil não exige uma instalação local do Python.

## Atualizações

Em **Configurações**, a opção **Procurar atualizações automaticamente** controla a verificação de novas versões publicadas no GitHub. Quando habilitada, a consulta é feita na inicialização. Também existe uma ação para verificar manualmente a qualquer momento.

Quando uma versão mais recente compatível com o canal atual é encontrada, o usuário escolhe se deseja baixá-la. Na distribuição portátil para Windows, o pacote é preparado para substituir os arquivos do aplicativo preservando a pasta `data/` e reiniciar o AnkiiStudio após a atualização. O atualizador aceita tanto o executável na raiz do ZIP quanto dentro de uma única pasta contêiner do build portátil.

## Roadmap

A página **Roadmap** apresenta o planejamento do projeto como uma linha do tempo. O conteúdo distribuído com o aplicativo fica em `ankiistudio/resources/roadmap.json`, separado do código da interface. Títulos, descrições e listas definidos nesse arquivo são exibidos exatamente no idioma em que forem escritos; somente os elementos fixos da página e os status são traduzidos pela interface.

Na primeira abertura da página durante a sessão, se houver conexão disponível, o AnkiiStudio tenta obter a versão pública mais recente desse arquivo no repositório GitHub. Se a consulta falhar, utiliza a última cópia em cache ou o arquivo incluído na versão instalada. Assim, alterações de planejamento podem ser publicadas por commit sem exigir uma nova versão apenas para atualizar o texto do Roadmap.

Os estados públicos utilizados são:

- `✓ CONCLUÍDO`;
- `◉ EM DESENVOLVIMENTO`;
- `◇ PLANEJADO`.

## Dados locais

Os dados criados durante o uso ficam na pasta `data/` da versão portátil:

```text
data/
├── database/
├── media/
│   ├── images/
│   └── audio/
├── exports/
├── cache/
└── logs/
```

Essa estrutura mantém projetos, mídias e arquivos de execução separados dos arquivos internos do aplicativo.

## Segurança e credenciais

As API keys configuradas pelo usuário não são armazenadas em texto simples dentro da pasta portátil.

O AnkiiStudio utiliza `keyring` para integrar-se ao gerenciador seguro de credenciais do sistema operacional.

Serviços externos podem exigir credenciais próprias, como:

- Google Gemini
- ElevenLabs
- Pixabay
- Pexels

Cada usuário deve utilizar suas próprias credenciais e respeitar os termos dos respectivos serviços.

## Desenvolvimento

Para executar o projeto a partir do código-fonte, utilize Python **3.11 ou superior**.

### Criar o ambiente virtual

```bat
py -3.14 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Caso utilize outra versão compatível do Python, ajuste o comando conforme sua instalação.

### Executar

```bat
python run.py
```

Ou diretamente:

```bat
.venv\Scripts\python.exe run.py
```

## Testes

Instale as dependências de desenvolvimento:

```bat
pip install -r requirements-dev.txt
```

Execute:

```bat
pytest
```

## Build para Windows

O projeto inclui um script para gerar a distribuição portátil:

```bat
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1
```

O processo utiliza PyInstaller e gera o pacote de distribuição na pasta `release/`.

## Estrutura do repositório

```text
AnkiiStudio/
├── ankiistudio/
│   ├── data/
│   ├── languages/
│   ├── resources/
│   ├── services/
│   └── ui/
├── scripts/
├── tests/
├── AnkiiStudio.spec
├── CHANGELOG.md
├── LICENSE
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
└── run.py
```

| Diretório | Finalidade |
|---|---|
| `ankiistudio/` | Código principal da aplicação |
| `ankiistudio/data/` | Conteúdo interno distribuído com o programa |
| `ankiistudio/languages/` | Pacotes de tradução da interface |
| `ankiistudio/resources/` | Ícones, Roadmap e demais recursos distribuídos |
| `ankiistudio/services/` | Serviços, integrações e regras de negócio |
| `ankiistudio/ui/` | Interface gráfica |
| `tests/` | Testes automatizados |
| `scripts/` | Scripts auxiliares e de build |

## Changelog

O histórico de alterações está disponível em [CHANGELOG.md](CHANGELOG.md).

## Licença

O AnkiiStudio é distribuído sob a **GNU General Public License v3.0 (GPL-3.0)**.

Consulte [LICENSE](LICENSE) para os termos completos.

Bibliotecas, APIs, serviços e mídias de terceiros permanecem sujeitos às suas próprias licenças e termos de uso.

## Autor

Desenvolvido por **Lucas Tsukasa**.

[GitHub @LucasTsukasa](https://github.com/LucasTsukasa)
