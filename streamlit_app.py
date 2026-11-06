"""Interface web do Stats RAG. Execute com: streamlit run streamlit_app.py."""

import json
import os
from urllib.parse import quote

import streamlit as st

from rag_web import RAIZ, buscar, carregar_corpus, compilar_pdf, gerar_slides, mensagem_erro
from web_conteudo import EXEMPLOS, MODELO_GERACAO, PERGUNTAS_SUGERIDAS


st.set_page_config(page_title="stats-rag · Da sua dúvida aos slides", page_icon="📚", layout="wide")
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


@st.dialog("Apresentação de exemplo", width="large")
def abrir_exemplo(exemplo):
    st.subheader(exemplo["titulo"])
    st.write(exemplo["pergunta"])
    pdf = (RAIZ / "exemplos" / exemplo["arquivo"]).read_bytes()
    st.pdf(pdf, height=560, key=f"leitor_{exemplo['id']}", alt=exemplo["titulo"])
    st.download_button(
        "Baixar apresentação em PDF", pdf, file_name=exemplo["arquivo"],
        mime="application/pdf", key=f"baixar_{exemplo['id']}",
    )


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
            if st.button("Abrir apresentação", key=f"exemplo_{exemplo['id']}", width="stretch"):
                abrir_exemplo(exemplo)


st.title("stats-rag: da sua dúvida aos slides")
st.write("Um agente que consulta os livros e cria uma apresentação para explicar sua dúvida de estatística.")

try:
    corpus = indice_salvo((RAIZ / "artifacts/manifest.json").read_bytes())
except Exception:
    st.error("Não foi possível carregar a biblioteca. Tente novamente em alguns instantes.")
    exibir_exemplos()
    st.stop()

chunks, indice, _, _ = corpus
# Credenciais vêm exclusivamente do servidor, nunca de campos da interface.
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
    st.caption(f"{len(chunks)} trechos para consultar")
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
    enviar = st.form_submit_button("Buscar nos livros", type="primary")

# Reserva o lugar da resposta antes dos exemplos, visíveis durante a consulta.
area_resposta = st.container()
exibir_exemplos()

with area_resposta:
    if enviar:
        st.session_state.pop("consulta_atual", None)
        st.session_state.pop("apresentacao", None)
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
        st.subheader("Configure o tema da apresentação")
        with st.form("slides"):
            tema = st.selectbox(
                "Tema", ["pixel", "ufabc"],
                format_func=lambda v: {"pixel": "Pixel", "ufabc": "UFABC"}[v],
            )
            with st.expander("Mais opções"):
                quantidade = st.slider("Máximo de slides", 2, 8, 4)
                autor = st.text_input("Autor da apresentação", max_chars=100)
            gerar = st.form_submit_button("Gerar apresentação", type="primary", disabled=not bool(chave))
        if not chave:
            st.caption("A geração de novas apresentações está temporariamente indisponível. As apresentações de exemplo podem ser abertas abaixo.")

        if gerar:
            st.session_state.pop("apresentacao", None)
            try:
                with st.spinner("Criando a apresentação… O Gemini pode levar alguns minutos para responder."):
                    dados, fontes = gerar_slides(
                        consulta["pergunta"], resultados, chave=chave,
                        modelo=MODELO_GERACAO,
                        tema=tema, quantidade=quantidade, autor=autor,
                    )
                st.session_state.apresentacao = {"dados": dados, "fontes": fontes, "tema": tema}
                with st.spinner("Preparando o PDF…"):
                    st.session_state.apresentacao["pdf"] = compilar_pdf(dados, tema)
            except Exception as erro:
                st.error(mensagem_erro(erro))
                if st.session_state.get("apresentacao"):
                    st.warning("O conteúdo está disponível em JSON. O PDF não foi gerado; tente menos conteúdo por slide.")

        apresentacao = st.session_state.get("apresentacao")
        if apresentacao:
            dados = apresentacao["dados"]
            st.subheader(dados["titulo"])
            if apresentacao.get("pdf"):
                st.download_button("Baixar apresentação em PDF", apresentacao["pdf"], "apresentacao_rag.pdf", "application/pdf", type="primary")
            with st.expander("Conteúdo e referências da apresentação"):
                st.download_button(
                    "Baixar conteúdo em JSON", json.dumps(dados, ensure_ascii=False, indent=2),
                    "slides.json", "application/json",
                )
                st.download_button(
                    "Baixar referências", json.dumps({"query": consulta["pergunta"], "fontes": apresentacao["fontes"]}, ensure_ascii=False, indent=2),
                    "fontes.json", "application/json",
                )
                for n, slide in enumerate(dados["slides"], 1):
                    st.markdown(f"**Slide {n} · {slide['campos']['titulo']}**")
                    for campo, texto in slide["campos"].items():
                        if campo not in {"titulo", "fontes", "autor"}:
                            st.write(texto)
                    st.caption(slide["campos"]["fontes"])

        with st.expander("Consultar as evidências encontradas"):
            st.caption(f"Pergunta: {consulta['pergunta']}")
            for resultado in resultados:
                c = resultado["chunk"]
                paginas = ", ".join(map(str, c.get("pdf_pages", []))) or "não informadas"
                with st.expander(f"[{resultado['referencia']}] {c['source']} · páginas {paginas}"):
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
