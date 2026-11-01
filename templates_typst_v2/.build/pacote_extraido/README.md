# Templates Typst — versão 2

Oito estruturas fixas, com textos editáveis em JSON: quatro Pixel e quatro UFABC.
O notebook `templates_typst_v2_colab.ipynb` incorpora os fontes, imagens e fontes
tipográficas. Abra-o no Google Colab e execute as células em ordem. Ele permite
salvar os arquivos no Drive e gerar o PDF sem API.

## Estruturas

| Sufixo do template | Campos |
| --- | --- |
| `abertura` | `titulo`, `apresentacao`, `autor`, `fontes` |
| `conceito` | `titulo`, `conteudo`, `fontes` |
| `comparacao` | `titulo`, `cabecalho_esquerdo`, `coluna_esquerda`, `cabecalho_direito`, `coluna_direita`, `fontes` |
| `formula` | `titulo`, `conteudo`, `formula`, `legenda`, `fontes` |

Use o prefixo `pixel_` ou `ufabc_`, por exemplo `pixel_conceito`.
O conteúdo aceita quantos parágrafos couberem; não há três tópicos obrigatórios.
Use `\n\n` para separar parágrafos e `\n` para uma quebra de linha.
Os campos são texto simples, sem interpretação de Markdown ou LaTeX.
O campo `formula` recebe matemática Typst, sem delimitadores `$`, por exemplo:

```text
"CV"_(k) = frac(1, k) sum_(i=1)^k "MSE"_i
```

## Tipografia e encaixe

- Títulos: 26 pt, com redução até 24 pt.
- Corpo: 18 pt, com redução até 16 pt, em passos de 0,5 pt.
- Comparação: cabeçalhos de 20 pt, com mínimo de 19 pt.
- Fórmula: 28 pt, com mínimo de 26 pt.
- Fontes bibliográficas e paginação: 10,5 pt.
- Pixel: Pixelify Sans, inclusive no corpo, com suporte a português.
- UFABC: Fira Sans. Equações: New Computer Modern Math nos dois temas.

As caixas mantêm posições e dimensões fixas. Se o texto não couber na fonte
mínima, a geração identifica o campo. Divida o conteúdo entre slides ou resuma-o;
o gerador não corta o texto. Tamanhos, mínimos e caixas ficam em `estruturas.json`.
As fontes tipográficas acompanham o pacote; a compilação ignora as fontes locais
do sistema para manter a reprodução em outra máquina.

## Fundos Pixel

1. Abertura: cubo de dados à direita, texto à esquerda.
2. Conceito: árvore pixelada à esquerda, texto à direita.
3. Comparação: nuvens de pontos à direita, duas colunas à esquerda.
4. Fórmula: matriz pixelada à esquerda, conteúdo à direita.

As ilustrações são decorativas e foram geradas com `image_gen` integrado.
Os prompts completos estão em `assets/prompts_pixel_v2.json`; a procedência das
fotografias, logotipos e fontes está em `assets/origem_assets.json`.

## Arquivos editáveis

- `conteudo.json`: exemplos baseados no texto de validação cruzada fornecido.
- `estruturas.json`: campos, caixas, cores e tamanhos por template.
- `temas.typ`: renderização e ajuste limitado da fonte.
- `main.typ`: entrada Typst.
- `gerar_slides.py`: função `gerar(...)`, usada pelo notebook.

Os exemplos preservam E1, E2 e E3 e as páginas do PDF informado pelo usuário.
A conversão da saída do Gemini para esses campos será uma etapa posterior.

## Uso em Python

Com `typst==0.15.0` instalado:

```python
from gerar_slides import gerar

resultado = gerar("conteudo.json", tema="pixel", destino="output/meus_slides.pdf")
```

`tema` aceita `todos`, `pixel` e `ufabc`. O retorno contém os caminhos do PDF e
das prévias PNG e a quantidade de slides gerados.
