"""Interface web do Stats RAG. Execute com: streamlit run streamlit_app.py."""

import json
import os
from urllib.parse import quote

import streamlit as st

from rag_web import RAIZ, buscar, carregar_corpus, compilar_pdf, gerar_slides, mensagem_erro


st.set_page_config(page_title="Stats RAG · Estatística com fontes", page_icon="📚", layout="wide")


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


st.title("Estatística, com as fontes à vista")
st.markdown("Faça uma pergunta sobre os livros, explore as evidências e transforme a explicação em slides.")

try:
    corpus = indice_salvo((RAIZ / "artifacts/manifest.json").read_bytes())
except Exception:
    st.error("Não foi possível carregar a biblioteca. Confira o manifesto e os arquivos da pasta artifacts.")
    st.stop()

chunks, indice, _, _ = corpus
with st.sidebar:
    st.header("Sua biblioteca")
    st.caption(f"{len(chunks)} trechos · {len(set(c['source'] for c in chunks))} capítulos do ISLP")
    st.markdown("**Capítulos disponíveis**\n\n5 · Resampling Methods\n\n7 · Moving Beyond Linearity\n\n8 · Tree-Based Methods")
    st.divider()
    chave_servidor = configuracao("GEMINI_API_KEY")
    chave_visitante = st.text_input(
        "Sua chave do Gemini (opcional)" if chave_servidor else "Sua chave do Gemini",
        type="password", key="chave_visitante",
        help="A chave fica na sessão, é usada no servidor e enviada apenas ao Gemini. Não é salva no repositório.",
    )
    chave = chave_visitante.strip() or chave_servidor
    if chave_servidor and not chave_visitante:
        st.caption("O Gemini está configurado pelo responsável pelo site.")
    elif not chave:
        st.caption("Sem chave, você pode explorar os textos pela busca lexical.")
    modo = st.selectbox(
        "Como buscar", ["Híbrida", "Lexical (sem API)"], index=0 if chave else 1,
        help="A híbrida combina termos e significado. A lexical procura palavras nos textos em inglês.",
    )
    st.caption("O uso do Gemini depende da cota disponível na sua chave.")

with st.form("consulta"):
    pergunta = st.text_area(
        "O que você quer estudar?", max_chars=2000, height=100,
        placeholder="Por exemplo: como k-fold e LOOCV diferem em viés, variância e custo computacional?",
    )
    enviar = st.form_submit_button("Buscar nos livros", type="primary")

if enviar:
    st.session_state.pop("consulta_atual", None)
    st.session_state.pop("apresentacao", None)
    if modo == "Híbrida" and not chave:
        st.warning("Informe uma chave do Gemini ou escolha a busca lexical.")
    else:
        try:
            with st.spinner("Procurando trechos relacionados…"):
                resultados = buscar(pergunta, corpus, chave=chave, modo=modo)
            st.session_state.consulta_atual = {"pergunta": pergunta.strip(), "resultados": resultados, "modo": modo}
        except Exception as erro:
            st.error(mensagem_erro(erro))

consulta = st.session_state.get("consulta_atual")
if not consulta:
    st.info("Comece com uma pergunta. Para testar sem API, busque em inglês: cross-validation, bootstrap ou regression trees.")
    st.stop()

st.subheader("Evidências encontradas")
st.caption(f"Pergunta: {consulta['pergunta']} · Busca: {consulta['modo']}")
resultados = consulta["resultados"]
if not resultados:
    st.info("Nenhum termo foi encontrado. Tente os termos do livro em inglês ou use a busca híbrida.")
    st.stop()

for resultado in resultados:
    c = resultado["chunk"]
    paginas = ", ".join(map(str, c.get("pdf_pages", []))) or "não informadas"
    titulo = f"[{resultado['referencia']}] {c['source']} · páginas {paginas}"
    with st.expander(titulo, expanded=resultado["referencia"] == "E1"):
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

st.divider()
st.subheader("Da pergunta à apresentação")
st.write("Os slides usam as três primeiras evidências e incluem referências às páginas dos livros.")
with st.form("slides"):
    esquerda, direita = st.columns(2)
    tema = esquerda.selectbox("Visual dos slides", ["pixel", "ufabc"], format_func=lambda v: {"pixel": "Pixel", "ufabc": "UFABC"}[v])
    quantidade = direita.slider("Máximo de slides", 2, 8, 4)
    autor = st.text_input("Autor da apresentação", max_chars=100)
    gerar = st.form_submit_button("Gerar apresentação", type="primary", disabled=not bool(chave))
if not chave:
    st.caption("Informe a chave do Gemini na barra lateral para gerar os slides.")

if gerar:
    st.session_state.pop("apresentacao", None)
    try:
        with st.spinner("Organizando a explicação com base nos livros…"):
            dados, fontes = gerar_slides(
                consulta["pergunta"], resultados, chave=chave,
                modelo=configuracao("GEMINI_MODEL", "gemini-3.8-flash"),
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
    st.download_button(
        "Baixar conteúdo em JSON", json.dumps(dados, ensure_ascii=False, indent=2),
        "slides.json", "application/json",
    )
    st.download_button(
        "Baixar referências", json.dumps({"query": consulta["pergunta"], "fontes": apresentacao["fontes"]}, ensure_ascii=False, indent=2),
        "fontes.json", "application/json",
    )
    for n, slide in enumerate(dados["slides"], 1):
        with st.expander(f"Slide {n} · {slide['campos']['titulo']}"):
            for campo, texto in slide["campos"].items():
                if campo not in {"titulo", "fontes", "autor"}:
                    st.write(texto)
            st.caption(slide["campos"]["fontes"])
