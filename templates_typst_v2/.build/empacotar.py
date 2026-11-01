"""Empacota os fontes e cria um notebook Colab autocontido."""
import ast
import base64
import io
import json
from pathlib import Path
import shutil
import textwrap
import zipfile

ROOT = Path(__file__).resolve().parent.parent

mono_bold = Path('/usr/share/fonts/opentype/fira/FiraMono-Bold.otf')
if mono_bold.exists():
    shutil.copy2(mono_bold, ROOT / 'assets/fonts' / mono_bold.name)

arquivos = [ROOT / name for name in (
    'main.typ', 'temas.typ', 'estruturas.json', 'conteudo.json',
    'gerar_slides.py', 'README.md',
)] + sorted((ROOT / 'assets').rglob('*'))
arquivos = [f for f in arquivos if f.is_file()]

buffer = io.BytesIO()
with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as z:
    for arquivo in arquivos:
        z.write(arquivo, arquivo.relative_to(ROOT).as_posix())

payload = base64.b64encode(buffer.getvalue()).decode('ascii')
(ROOT / 'output/templates_typst_v2_fontes.zip').write_bytes(buffer.getvalue())

def markdown(text):
    return {'cell_type': 'markdown', 'metadata': {}, 'source': textwrap.dedent(text).strip() + '\n'}

def code(text, *, hidden=False):
    metadata = {'cellView': 'form'} if hidden else {}
    return {
        'cell_type': 'code', 'metadata': metadata,
        'source': textwrap.dedent(text).strip() + '\n',
        'execution_count': None, 'outputs': [],
    }

cells = [
    markdown('''
        # Slides em Typst: Pixel e UFABC — versão 2

        Este notebook contém os oito templates, imagens e fontes necessários.
        Execute as células em ordem. O PDF é produzido a partir de texto estruturado,
        sem chamada à API e sem precisar do PowerPoint.

        Cada tema oferece **abertura, conceito, comparação e fórmula**.
        As configurações ficam separadas da execução. Os arquivos do pacote serão
        preparados na pasta escolhida e podem ser editados pelo painel de arquivos.
    '''),
    markdown('## 1. Instalação e bibliotecas'),
    code('''
        %pip install -q "typst==0.15.0"

        import base64
        import importlib.util
        import io
        import json
        import zipfile
        from pathlib import Path

        from google.colab import drive, files
        from IPython.display import Image, display
    '''),
    markdown('## 2. Parâmetros'),
    code('''
        USAR_DRIVE = True
        TEMA_ESCOLHIDO = "todos"  # "todos", "pixel" ou "ufabc"
        NOME_PDF = "slides_typst_v2.pdf"
        GERAR_PREVIAS = True

        PASTA_DRIVE = Path("/content/drive/MyDrive/rag_estatistica/templates_typst_v2")
        PASTA_LOCAL = Path("/content/rag_estatistica/templates_typst_v2")
        PASTA_TEMPLATES = PASTA_DRIVE if USAR_DRIVE else PASTA_LOCAL
    '''),
    markdown('''
        ## 3. Preparar os templates

        A célula abaixo contém o pacote incorporado. Não é necessário editar seu
        conteúdo. Ela preserva os arquivos já existentes, inclusive textos que você
        tenha alterado no Drive.
    '''),
    code(
        '#@title Preparar arquivos, fontes e imagens dos oito templates\n'
        'if USAR_DRIVE:\n'
        '    drive.mount("/content/drive")\n\n'
        'PASTA_TEMPLATES.mkdir(parents=True, exist_ok=True)\n'
        'PACOTE_TEMPLATES_B64 = "' + payload + '"\n\n'
        'with zipfile.ZipFile(io.BytesIO(base64.b64decode(PACOTE_TEMPLATES_B64))) as pacote:\n'
        '    for nome in pacote.namelist():\n'
        '        caminho = PASTA_TEMPLATES / nome\n'
        '        caminho.parent.mkdir(parents=True, exist_ok=True)\n'
        '        if not caminho.exists():\n'
        '            caminho.write_bytes(pacote.read(nome))\n\n'
        'print("Templates disponíveis em:", PASTA_TEMPLATES)\n',
        hidden=True,
    ),
    markdown('''
        ## 4. Conteúdo

        Carregue os exemplos. Para experimentar, altere uma string no dicionário
        `dados_slides` e execute novamente a geração. Comece mudando apenas o título.

        O campo `formula` usa matemática Typst, sem `$`, por exemplo:
        `"CV"_(k) = frac(1, k) sum_(i=1)^k "MSE"_i`.
        Os outros campos recebem texto simples.
    '''),
    code('''
        ARQUIVO_CONTEUDO = PASTA_TEMPLATES / "conteudo.json"

        dados_slides = json.loads(ARQUIVO_CONTEUDO.read_text(encoding="utf-8"))
        print("Modelos carregados:")
        for indice, slide in enumerate(dados_slides["slides"]):
            print(indice, slide["template_id"], list(slide["campos"]))
    '''),
    code('''
        # Edite os textos aqui, antes de gerar o PDF.
        dados_slides["slides"][0]["campos"]["titulo"] = "Viés e variância na validação cruzada"

        # Outro exemplo de alteração:
        # dados_slides["slides"][5]["campos"]["conteudo"] = "Sua explicação aqui."
    '''),
    markdown('''
        ## 5. Gerar o PDF

        As posições das caixas permanecem fixas. Os títulos começam em 26 pt e o
        corpo em 18 pt, com redução até 24 e 16 pt, respectivamente. Se o texto
        ainda não couber, a mensagem identifica o campo: resuma-o ou distribua
        o conteúdo em outro slide. Não há quantidade fixa de parágrafos.

        Para mudar cores, tamanhos e o limite de redução, edite `estruturas.json`.
    '''),
    code('''
        ARQUIVO_PDF = PASTA_TEMPLATES / "output" / NOME_PDF

        especificacao = importlib.util.spec_from_file_location(
            "gerador_templates_typst", PASTA_TEMPLATES / "gerar_slides.py"
        )
        gerador_templates = importlib.util.module_from_spec(especificacao)
        especificacao.loader.exec_module(gerador_templates)

        resultado_slides = gerador_templates.gerar(
            dados_slides,
            raiz=PASTA_TEMPLATES,
            tema=TEMA_ESCOLHIDO,
            destino=ARQUIVO_PDF,
            previas=GERAR_PREVIAS,
        )

        print("Slides gerados:", resultado_slides["total_slides"])
        print("PDF:", resultado_slides["pdf"])
    '''),
    markdown('## 6. Conferir as prévias'),
    code('''
        for numero, imagem in enumerate(resultado_slides["previas"], start=1):
            print("SLIDE", numero)
            display(Image(filename=str(imagem), width=960))
    '''),
    markdown('''
        ## 7. Salvar conteúdo e baixar PDF

        Execute esta célula para guardar suas alterações no JSON e baixar o PDF.
        Se você trocar o tema ou os textos, gere novamente antes de baixar.
    '''),
    code('''
        ARQUIVO_CONTEUDO.write_text(
            json.dumps(dados_slides, ensure_ascii=False, indent=2) + "\\n",
            encoding="utf-8",
        )
        files.download(str(resultado_slides["pdf"]))
    '''),
]

notebook = {
    'nbformat': 4, 'nbformat_minor': 5,
    'metadata': {
        'colab': {'name': 'templates_typst_v2_colab.ipynb', 'provenance': []},
        'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
        'language_info': {'name': 'python'},
    },
    'cells': cells,
}
for i, cell in enumerate(cells):
    cell['id'] = f'typst-{i:02d}'
    if cell['cell_type'] == 'code':
        source = '\n'.join(line for line in cell['source'].splitlines()
                           if not line.lstrip().startswith('%'))
        ast.parse(source)

path = ROOT / 'templates_typst_v2_colab.ipynb'
path.write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
with zipfile.ZipFile(ROOT / 'output/templates_typst_v2_fontes.zip', 'w', compression=zipfile.ZIP_DEFLATED) as z:
    for arquivo in arquivos + [path]:
        z.write(arquivo, arquivo.relative_to(ROOT).as_posix())
print('Notebook:', path)
print('Pacote-fonte:', ROOT / 'output/templates_typst_v2_fontes.zip')
print('Arquivos incorporados:', len(arquivos))
