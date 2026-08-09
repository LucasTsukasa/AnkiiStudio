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
- Exportação direta para `.apkg`.
- Organização em baralhos e subbaralhos.
- Suporte a múltiplos idiomas.
- Modelos de flashcards prontos para idiomas compatíveis.
- Modelo personalizado para criação de estruturas próprias.
- Geração de conteúdo com Google Gemini.
- Importação de conteúdo estruturado por JSON/TXT.
- Busca e processamento de imagens pelo Wikimedia Commons.
- Áudio por Wikimedia Commons, VOICEVOX, Gemini TTS e ElevenLabs.
- Perfis de voz configuráveis por idioma.
- Ajustes de voz por provedor.
- Reprodução de áudio dentro do aplicativo.
- Tema claro e escuro.
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

## Criação de conteúdo

O AnkiiStudio oferece diferentes formas de adicionar conteúdo aos projetos.

### Conteúdo com IA

A integração com **Google Gemini** permite gerar conteúdo estruturado de acordo com o idioma, modelo e configuração definidos no projeto.

### Importação

Também é possível importar conteúdo previamente preparado em formatos estruturados, permitindo utilizar respostas geradas externamente ou materiais próprios.

### Conteúdo interno

Alguns modelos podem utilizar conteúdo fornecido diretamente pelo AnkiiStudio, sem necessidade de geração por IA.

## Imagens

O AnkiiStudio utiliza o **Wikimedia Commons** como fonte de imagens.

O aplicativo pesquisa, seleciona e processa as mídias antes de vinculá-las aos cartões, incluindo suporte a imagens rasterizadas provenientes de arquivos vetoriais disponíveis no Commons.

Quando disponíveis, informações de origem, autoria e licença são preservadas internamente.

## Áudio

O AnkiiStudio pode utilizar diferentes provedores de áudio.

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
| `ankiistudio/resources/` | Ícones e recursos visuais |
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
