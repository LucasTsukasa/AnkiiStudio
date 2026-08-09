# AnkiiStudio

<p align="center">
  <img src="ankiistudio/resources/icons/app.png" alt="AnkiiStudio" width="150">
</p>

<p align="center">
  Aplicativo desktop para criar, revisar e exportar flashcards para o Anki com conteúdo estruturado, imagens e áudio.
</p>

<p align="center">
  <img alt="Version" src="https://img.shields.io/badge/version-0.10.0-19D978">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.11%2B-3776AB">
  <img alt="Platform" src="https://img.shields.io/badge/Windows-portable-0078D4">
  <img alt="License" src="https://img.shields.io/badge/license-GPL--3.0-blue">
</p>

## Sobre

O **AnkiiStudio** organiza a criação de flashcards e exporta projetos em `.apkg`, sem exigir AnkiConnect. A versão atual prioriza uma experiência portátil para Windows: dados de projetos, banco local, mídias, cache e logs ficam dentro da pasta `data/` ao lado do aplicativo.

As credenciais de serviços externos não ficam dentro dessa pasta. As chaves configuradas pela interface são armazenadas pelo gerenciador seguro de credenciais do sistema por meio de `keyring`.

## Recursos principais

- Projetos de flashcards com frente e verso configuráveis.
- Exportação para `.apkg`.
- Subbaralhos organizados com a estrutura `Baralho::Subbaralho`.
- Geração/importação de conteúdo com suporte a Gemini e importação JSON/TXT.
- Imagens pelo Wikimedia Commons, com metadados de autoria/licença preservados internamente.
- Áudio por Wikimedia, VOICEVOX, Gemini TTS e ElevenLabs.
- Perfis ilimitados de voz Gemini e ElevenLabs separados por idioma.
- Ajustes de voz no ElevenLabs e VOICEVOX.
- Reprodução de exemplo do VOICEVOX dentro do próprio AnkiiStudio.
- Pesquisa por relevância nos seletores de modelo, idioma e personagem/estilo do VOICEVOX sem ocultar resultados, mantendo a digitação ativa enquanto a lista está aberta.
- Tema escuro e claro.
- Interface responsiva para uso em janela portátil.

## Idiomas

A interface inclui um catálogo amplo com **184 idiomas ISO 639-1**, pesquisáveis diretamente no mesmo seletor. Entre eles estão Japonês, Inglês, Espanhol, Coreano, Português, Francês, Alemão, Italiano, Chinês, Árabe, Russo, Hindi e muitos outros.

A arquitetura de projetos e perfis de voz não está mais limitada aos quatro idiomas das versões anteriores. Códigos ISO/BCP-47 válidos também são normalizados internamente.

Na versão 0.10.0, os modelos padrão revisados estão disponíveis para **Japonês**:

- Hiragana
- Katakana
- Frases Básicas

Para todos os idiomas existe o modelo **Personalizado**, que é a opção inicial da tela Criar.

## Modelos padrão

Modelos padrão utilizam o conteúdo interno revisado e não pedem configurações que alterariam esse conteúdo. Ao selecionar um modelo padrão:

- Tema/contexto fica bloqueado.
- Quantidade é definida pelo próprio modelo.
- O método de criação fica bloqueado em **Conteúdo padrão**.
- A estrutura visual do flashcard continua editável.

A estrutura inicial recomendada é carregada automaticamente. O usuário pode remover, adicionar ou reorganizar os componentes antes de criar o projeto.

## Estrutura dos cartões

A estrutura visual foi simplificada para componentes que possuem função direta no cartão:

- Imagem
- Conteúdo principal
- Leitura
- Romaji / Romanização
- Tradução
- Áudio
- Exemplo
- Explicação
- Mnemônico

Existe apenas um componente **Áudio**. Ele sempre sintetiza o **Conteúdo principal** do cartão, seja uma palavra, frase, kana ou outro item. O áudio não força a criação de uma frase de exemplo.

Campos antigos continuam reconhecidos internamente para abrir projetos anteriores, mas são normalizados para a estrutura atual.

## Busca de imagens

Na busca automática, o AnkiiStudio usa uma ordem determinística:

1. conteúdo original do cartão;
2. tradução, somente como fallback.

Termos de imagem inventados por IA não são usados automaticamente. Isso evita transformar um kana isolado, por exemplo, em uma associação semântica não solicitada.

Arquivos **SVG do Wikimedia Commons são aceitos**. O AnkiiStudio solicita uma miniatura rasterizada de até 900 px ao próprio Wikimedia e processa essa versão com Pillow, evitando descartar ilustrações vetoriais limpas de kana, kanji, símbolos e diagramas. Para SVGs com fundo transparente, a miniatura é composta explicitamente sobre branco antes de virar WebP, evitando blocos pretos em visualizadores que não preservam corretamente o canal alfa. A ordem de relevância retornada pela pesquisa do Commons é preservada.

## Áudio

### Wikimedia Commons

Prioriza gravações humanas quando houver mídia compatível.

### VOICEVOX

Para projetos em japonês, o AnkiiStudio consulta os personagens/estilos disponíveis no engine local. O seletor aceita pesquisa por relevância e continua exibindo todas as vozes.

É possível ajustar por projeto:

- velocidade;
- tom;
- entonação;
- volume;
- escala de pausas.

O botão **Ouvir exemplo** reproduz o resultado diretamente no AnkiiStudio, sem abrir um player externo.

### Gemini TTS

Perfis de voz são cadastrados por idioma e podem combinar diferentes modelos e vozes. O modo inteligente pode percorrer os perfis habilitados e respeita bloqueios temporários de cota observados durante a execução.

### ElevenLabs

Cada perfil pode definir:

- idioma;
- nome;
- Model ID;
- Voice ID;
- estabilidade;
- similaridade;
- estilo;
- velocidade;
- Speaker Boost.

Erros HTTP retornados pela ElevenLabs têm a mensagem da API preservada no diagnóstico. Falhas permanentes de um perfil durante um lote são bloqueadas para o restante daquele lote, evitando repetir a mesma requisição inválida em todos os cartões.

Para `eleven_multilingual_v2`, o AnkiiStudio não força `language_code` nem a normalização japonesa específica que causava o erro `Language text normalization is not supported for language code 'None'`; a normalização geral permanece em modo automático.

## Mídia ausente e exportação

Uma mídia ausente não bloqueia automaticamente o projeto. Se o cartão continuar possuindo uma frente válida, o AnkiiStudio avisa quais mídias estão faltando e permite exportar mesmo assim. O componente vazio é omitido no cartão final.

A exportação só é bloqueada quando a ausência deixa a frente do cartão sem conteúdo utilizável.

## Quantidade de cartões no Anki

O AnkiiStudio grava no `.apkg` todos os cartões selecionados para exportação. Se, depois da importação, a tela de estudo do Anki mostrar um número menor de **cartões novos**, verifique o limite diário de Novos nas opções do baralho. O navegador do Anki pode ser usado para confirmar a quantidade total realmente importada.

## Dados da versão portátil

Ao executar o código-fonte ou o build portátil, os dados não sensíveis ficam em:

```text
AnkiiStudio/
├── AnkiiStudio.exe
└── data/
    ├── database/
    │   └── ankiistudio.db
    ├── media/
    │   ├── images/
    │   └── audio/
    ├── exports/
    ├── cache/
    └── logs/
```

A pasta `data/` é criada automaticamente. Ela não faz parte do repositório Git.

As API keys são configuradas em **Configurações** e permanecem no gerenciador de credenciais do Windows. O projeto não depende de `.env` para o uso normal.

## Executar pelo código-fonte

Requer Python 3.11 ou superior. No ambiente de desenvolvimento atualmente utilizado, Python 3.14 pode ser usado assim:

```bat
py -3.14 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
python run.py
```

Sem ativar o ambiente:

```bat
.venv\Scripts\python.exe run.py
```

## Testes

```bat
pip install -r requirements-dev.txt
pytest
```

## Build portátil para Windows

```bat
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1
```

O script executa os testes, gera o aplicativo com PyInstaller e cria:

```text
dist\AnkiiStudio\AnkiiStudio.exe
release\AnkiiStudio-Portable-0.10.0.zip
```

A pasta `data/` é preparada junto do build portátil.

## Publicação no GitHub

O repositório deve conter o código-fonte e os arquivos de desenvolvimento. O pacote compilado deve ser publicado em **GitHub Releases**, por exemplo `AnkiiStudio-Portable-0.10.0.zip`.

Arquivos locais como `.venv/`, `data/`, `build/`, `dist/`, `release/`, caches, bancos e segredos são ignorados pelo Git.

## Licença

O código do AnkiiStudio é distribuído sob a **GNU General Public License v3.0 (GPL-3.0)**. Consulte [LICENSE](LICENSE).

Bibliotecas, serviços e mídias de terceiros mantêm seus próprios termos e licenças. O AnkiiStudio preserva metadados de mídia quando aplicável, sem inserir créditos técnicos em cada flashcard.

## Autor

**Lucas Tsukasa**  
GitHub: [@LucasTsukasa](https://github.com/LucasTsukasa)
