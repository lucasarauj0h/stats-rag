"""Interface web do Stats RAG. Execute com: streamlit run streamlit_app.py."""

import json
import os
from urllib.parse import quote, urlencode, urlsplit, urlunsplit

import streamlit as st

from rag_web import RAIZ, buscar, carregar_corpus, compilar_pdf, gerar_slides, mensagem_erro
from web_apresentacoes import CatalogoApresentacoes, salvar_pdf
from web_conteudo import EXEMPLOS, MODELO_GERACAO, PERGUNTAS_SUGERIDAS


st.set_page_config(page_title="stats-rag", page_icon="📚", layout="wide")
st.markdown(
    """<style>
    [role="listbox"] [role="option"] {white-space: normal; height: auto;}
    [role="listbox"] [role="option"] span {white-space: normal;}
    .st-key-pergunta [data-baseweb="select"] > div {min-height: 3.2rem;}
    </style>""",
    unsafe_allow_html=True,
)


def configuracao(nome, padrao=""):
    valor = os.environ.get(nome)
    if valor:
        return valor
    try:
        return st.secrets.get(nome, padrao)
    except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        return padrao


@st.cache_resource(show_spinner="Carregando a biblioteca…")
def indice_salvo(assinatura):
    return carregar_corpus()


@st.cache_resource
def catalogo_apresentacoes():
    return CatalogoApresentacoes()


def link_apresentacao(tipo, identificador):
    # Remove o caminho interno do iframe da hospedagem, preservando o domínio atual.
    origem = urlsplit(st.context.url or "http://localhost:8501/")
    return urlunsplit((origem.scheme, origem.netloc, "/", urlencode({tipo: identificador}), ""))


def link_pdf(arquivo):
    origem = urlsplit(st.context.url or "http://localhost:8501/")
    return urlunsplit((origem.scheme, origem.netloc, "/app/static/" + quote(arquivo, safe="/"), "", ""))


def link_leitor(arquivo):
    return link_pdf("apresentacao.html") + "?" + urlencode({"arquivo": arquivo})


def abrir_pdf_direto(arquivo):
    # O link é uma alternativa caso o navegador impeça o redirecionamento automático.
    st.link_button("Ver apresentação", link_leitor(arquivo), type="primary")
    st.link_button("PDF direto", link_pdf(arquivo))
    st.html(
        f"<script>window.top.location.replace({json.dumps(link_leitor(arquivo))});</script>",
        unsafe_allow_javascript=True,
    )


def abrir_pagina_apresentacao():
    exemplo_id = st.query_params.get("exemplo")
    token = st.query_params.get("apresentacao")
    if exemplo_id:
        exemplo = next((e for e in EXEMPLOS if e["id"] == exemplo_id), None)
        if exemplo is None:
            st.error("Apresentação não encontrada.")
        else:
            abrir_pdf_direto("apresentacoes/" + exemplo["arquivo"])
        st.stop()
    if token:
        pedido = catalogo_apresentacoes().obter(token)
        if pedido is None:
            st.info("Este link expirou ou o servidor reiniciou. Volte à consulta e gere a apresentação novamente.")
            st.stop()
        try:
            with pedido.bloqueio:
                if pedido.pdf is None:
                    chave = configuracao("GEMINI_API_KEY")
                    if not chave:
                        st.warning("A geração está temporariamente indisponível.")
                        st.stop()
                    with st.spinner("Criando sua apresentação… O Gemini pode levar alguns minutos para responder."):
                        dados, _ = gerar_slides(
                            pedido.pergunta, pedido.resultados, chave=chave,
                            modelo=MODELO_GERACAO, tema=pedido.tema,
                            quantidade=pedido.quantidade, autor="",
                        )
                        if pedido.titulo:
                            dados["titulo"] = pedido.titulo
                            for slide in dados["slides"]:
                                if slide["template_id"].endswith("_abertura"):
                                    slide["campos"]["titulo"] = pedido.titulo
                        pdf = compilar_pdf(dados, pedido.tema)
                        salvar_pdf(token, pdf)
                        pedido.pdf = pdf
            abrir_pdf_direto(f"geradas/{token}.pdf")
        except Exception as erro:
            st.error(mensagem_erro(erro))
            st.caption("Você pode tentar recarregar esta guia ou consultar os exemplos na página inicial.")
        st.stop()


def exibir_exemplos():
    st.divider()
    st.subheader("Veja uma dúvida virar apresentação")
    st.write(
        "A API gratuita do Gemini pode falhar ou levar alguns minutos para responder. "
        "Enquanto isso, explore três exemplos de perguntas e apresentações já geradas."
    )
    for coluna, exemplo in zip(st.columns(len(EXEMPLOS)), EXEMPLOS):
        with coluna.container(border=True):
            st.caption(f"Capítulo {exemplo['capitulo']} · {exemplo['slides']} slides")
            st.markdown(f"**{exemplo['titulo']}**")
            st.write(exemplo["pergunta"])
            st.link_button(
                "Ver apresentação", link_leitor("apresentacoes/" + exemplo["arquivo"]),
                width="stretch",
            )
            st.link_button("PDF direto", link_pdf("apresentacoes/" + exemplo["arquivo"]), width="stretch")


# A guia da geração redireciona para o PDF final, sem carregar um leitor no Streamlit.
abrir_pagina_apresentacao()

st.image(str(RAIZ / "assets/stats-rag.svg"), width=330)
st.write("Um agente que consulta os livros e cria uma apresentação para explicar sua dúvida de estatística.")

try:
    corpus = indice_salvo((RAIZ / "artifacts/manifest.json").read_bytes())
except Exception:
    st.error("Não foi possível carregar a biblioteca. Tente novamente em alguns instantes.")
    exibir_exemplos()
    st.stop()

chunks, indice, _, _ = corpus
st.session_state.pop("chave_visitante", None)
chave = configuracao("GEMINI_API_KEY")
with st.sidebar:
    st.header("Sobre o corpus")
    st.markdown(
        "O corpus reúne **3 capítulos** do livro "
        "***An Introduction to Statistical Learning***, na edição com Python."
    )
    st.markdown("O livro é disponibilizado gratuitamente em [statlearning.com](https://www.statlearning.com/).")
    st.markdown("**Capítulos disponíveis**\n\n5 · Resampling Methods\n\n7 · Moving Beyond Linearity\n\n8 · Tree-Based Methods")
    st.caption(f"{len(chunks)} chunkings")
    with st.expander("Opções da busca"):
        modo = st.selectbox(
            "Como buscar", ["Híbrida", "Lexical (sem API)"], index=0 if chave else 1,
            format_func=lambda v: {"Híbrida": "Por significado e palavras", "Lexical (sem API)": "Por palavras"}[v],
            help="A busca por palavras compara sua pergunta com os textos em inglês do livro.",
            key="modo_busca",
        )

with st.form("consulta"):
    pergunta = st.selectbox(
        "Qual é a sua dúvida?", PERGUNTAS_SUGERIDAS, index=None,
        accept_new_options=True, key="pergunta",
        placeholder="Escreva sua pergunta ou escolha uma sugestão",
    )
    st.caption("Você pode perguntar em português ou inglês. Para escrever uma pergunta própria, digite e pressione Enter.")
    enviar = st.form_submit_button("Buscar no livro", type="primary")

area_resposta = st.container()
exibir_exemplos()

with area_resposta:
    if enviar:
        st.session_state.pop("consulta_atual", None)
        st.session_state.pop("link_apresentacao", None)
        if modo == "Híbrida" and not chave:
            st.warning("A busca por significado está temporariamente indisponível. Você pode buscar por palavras e explorar os exemplos.")
        else:
            try:
                with st.spinner("Procurando trechos relacionados à sua dúvida…"):
                    resultados = buscar(pergunta or "", corpus, chave=chave, modo=modo)
                st.session_state.consulta_atual = {"pergunta": pergunta.strip(), "resultados": resultados, "modo": modo}
            except Exception as erro:
                st.error(mensagem_erro(erro))

    consulta = st.session_state.get("consulta_atual")
    if consulta and consulta["resultados"]:
        resultados = consulta["resultados"]
        st.subheader("Configure sua apresentação")
        coluna_tema, coluna_paginas, coluna_titulo = st.columns(3)
        tema = coluna_tema.selectbox(
            "Tema", ["pixel", "ufabc"],
            format_func=lambda v: {"pixel": "Pixel", "ufabc": "UFABC"}[v],
        )
        quantidade = coluna_paginas.number_input("Número de páginas", min_value=2, max_value=8, value=4, step=1)
        titulo = coluna_titulo.text_input("Título", max_chars=60, placeholder="Título da apresentação (opcional)")
        assinatura = (consulta["pergunta"], tuple(r["chunk"]["chunk_id"] for r in resultados), tema, quantidade, titulo)
        catalogo = catalogo_apresentacoes()
        link_atual = st.session_state.get("link_apresentacao")
        if not link_atual or link_atual["assinatura"] != assinatura or catalogo.obter(link_atual["token"]) is None:
            token = catalogo.adicionar(
                pergunta=consulta["pergunta"], resultados=resultados, tema=tema,
                quantidade=quantidade, titulo=titulo,
            )
            link_atual = {"assinatura": assinatura, "token": token}
            st.session_state.link_apresentacao = link_atual
        pedido = catalogo.obter(link_atual["token"])
        st.link_button(
            "Ver apresentação" if pedido.pdf is not None else "Gerar apresentação",
            link_leitor(f"geradas/{link_atual['token']}.pdf") if pedido.pdf is not None else link_apresentacao("apresentacao", link_atual["token"]),
            type="primary", disabled=not bool(chave),
        )
        if not chave:
            st.caption("A geração de novas apresentações está temporariamente indisponível. As apresentações de exemplo podem ser abertas abaixo.")

        with st.expander("Consultar as evidências encontradas", expanded=True):
            st.caption(f"Pergunta: {consulta['pergunta']}")
            for resultado in resultados:
                c = resultado["chunk"]
                paginas = ", ".join(map(str, c.get("pdf_pages", []))) or "não informadas"
                with st.expander(f"[{resultado['referencia']}] {c['source']} · páginas {paginas}", expanded=resultado["referencia"] == "E1"):
                    st.caption(c.get("section_title") or "Seção não identificada")
                    st.text(c["content"])
                    caminho_pdf = RAIZ / "corpus" / c["source"]
                    if caminho_pdf.is_file():
                        st.download_button(
                            "Baixar capítulo original", caminho_pdf.read_bytes(), file_name=c["source"],
                            mime="application/pdf", key=f"pdf_{c['chunk_id']}",
                        )
                    else:
                        st.link_button(
                            "Abrir capítulo original",
                            f"https://github.com/lucasarauj0h/stats-rag/blob/main/corpus/{quote(c['source'])}",
                        )
    elif consulta:
        st.info("Nenhum termo foi encontrado. Tente os termos do livro em inglês ou explore os exemplos abaixo.")
