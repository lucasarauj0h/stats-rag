"""Preenche os templates Typst a partir de um dicionário ou arquivo JSON."""

import argparse
import json
from pathlib import Path

import typst


def gerar(conteudo, *, raiz=None, tema="todos", destino=None, previas=True):
    """Gera PDF e prévias; reutiliza os assets e não realiza chamadas à API."""
    raiz = Path(raiz or Path(__file__).resolve().parent).resolve()
    if isinstance(conteudo, (str, Path)):
        conteudo = json.loads(Path(conteudo).read_text(encoding="utf-8"))

    estruturas = json.loads((raiz / "estruturas.json").read_text(encoding="utf-8"))
    layouts = {item["template_id"]: item for item in estruturas["layouts"]}
    if tema not in {"todos", "pixel", "ufabc"}:
        raise ValueError("Escolha tema='todos', 'pixel' ou 'ufabc'.")

    slides = [
        slide for slide in conteudo["slides"]
        if tema == "todos" or layouts[slide["template_id"]]["tema"] == tema
    ]
    if not slides:
        raise ValueError("Não há slides para o tema escolhido.")

    for slide in slides:
        esperados = [c["nome"] for c in layouts[slide["template_id"]]["campos"]]
        faltantes = [nome for nome in esperados if nome not in slide["campos"]]
        if faltantes:
            raise ValueError(
                f"Campos ausentes no template {slide['template_id']}: {faltantes}"
            )

    dados = {**conteudo, "slides": slides}
    destino = Path(destino or raiz / "output" / "templates_typst_v2.pdf").resolve()
    destino.parent.mkdir(parents=True, exist_ok=True)

    opcoes = {
        "root": str(raiz),
        "font_paths": [str(raiz / "assets" / "fonts")],
        "ignore_system_fonts": True,
        "sys_inputs": {"conteudo": json.dumps(dados, ensure_ascii=False)},
    }
    entrada = str(raiz / "main.typ")
    pdf = typst.compile(entrada, **opcoes)
    destino.write_bytes(pdf)

    imagens = []
    if previas:
        pasta_previas = destino.parent / (destino.stem + "_previas")
        pasta_previas.mkdir(parents=True, exist_ok=True)
        typst.compile(
            entrada,
            output=str(pasta_previas / "slide-{n}.png"),
            format="png",
            ppi=120,
            **opcoes,
        )
        imagens = [pasta_previas / f"slide-{i}.png" for i in range(1, len(slides) + 1)]

    return {"pdf": destino, "previas": imagens, "total_slides": len(slides)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--conteudo", type=Path)
    parser.add_argument("--tema", choices=["todos", "pixel", "ufabc"], default="todos")
    parser.add_argument("--saida", type=Path)
    parser.add_argument("--sem-previas", action="store_true")
    args = parser.parse_args()
    pasta = Path(__file__).resolve().parent
    resultado = gerar(
        args.conteudo or pasta / "conteudo.json",
        raiz=pasta,
        tema=args.tema,
        destino=args.saida,
        previas=not args.sem_previas,
    )
    print("Slides:", resultado["total_slides"])
    print("PDF:", resultado["pdf"])
