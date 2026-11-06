"""Validação local sem chamadas pagas: índice real, respostas simuladas e PDF real."""

import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from rag_web import (
    RAIZ, buscar, carregar_corpus, cliente_gemini, compilar_pdf,
    gerar_slides, mensagem_erro, montar_contexto, validar_slides,
)


class RagWebTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus = carregar_corpus()

    def test_indice_real_e_busca_lexical_sem_api(self):
        chunks, indice, _, _ = self.corpus
        self.assertEqual(indice["matriz"].shape, (len(chunks), 3072))
        with patch("rag_web.cliente_gemini", side_effect=AssertionError("API inesperada")):
            resultados = buscar("cross-validation LOOCV", self.corpus, modo="Lexical (sem API)")
        self.assertTrue(resultados)
        self.assertEqual(resultados[0]["chunk"]["source"], "ISLP-5.pdf")
        self.assertFalse(buscar("zzzzzzzzzzxyz", self.corpus, modo="Lexical (sem API)"))
        self.assertEqual(len({r["chunk"]["chunk_id"] for r in resultados}), len(resultados))

    def test_pergunta_invalida_nao_chama_api(self):
        with patch("rag_web.cliente_gemini", side_effect=AssertionError("API inesperada")):
            for pergunta in ("", " ", "???", "a" * 2001):
                with self.assertRaises(ValueError):
                    buscar(pergunta, self.corpus, chave="teste")

    def test_busca_hibrida_usa_modelo_e_formato_do_manifesto(self):
        cliente = MagicMock()
        vetor = self.corpus[1]["matriz"][0]
        cliente.models.embed_content.return_value = SimpleNamespace(
            embeddings=[SimpleNamespace(values=vetor.tolist())]
        )
        with patch("rag_web.cliente_gemini") as fabrica:
            fabrica.return_value.__enter__.return_value = cliente
            resultados = buscar("cross-validation", self.corpus, chave="teste")
        parametros = cliente.models.embed_content.call_args.kwargs
        self.assertEqual(parametros["model"], self.corpus[1]["config"]["modelo"])
        self.assertEqual(parametros["contents"], "task: search result | query: cross-validation")
        self.assertEqual(parametros["config"].output_dimensionality, 3072)
        self.assertEqual(len(resultados), 5)
        # A fusão pode priorizar outro trecho; confira o alinhamento texto-vetor.
        for resultado in resultados:
            posicao = self.corpus[1]["chunk_ids"].index(resultado["chunk"]["chunk_id"])
            esperado = float(self.corpus[1]["matriz"][posicao] @ vetor)
            self.assertAlmostEqual(resultado["similaridade"], esperado, places=5)
        self.assertTrue(all(-1 <= r["similaridade"] <= 1 for r in resultados))

    def test_embedding_incompativel_e_rejeitado(self):
        cliente = MagicMock()
        cliente.models.embed_content.return_value = SimpleNamespace(
            embeddings=[SimpleNamespace(values=[0.0, 0.0])]
        )
        with patch("rag_web.cliente_gemini") as fabrica:
            fabrica.return_value.__enter__.return_value = cliente
            with self.assertRaisesRegex(ValueError, "índice salvo"):
                buscar("cross-validation", self.corpus, chave="teste")

    def test_fontes_desconhecidas_e_formula_invalida_sao_rejeitadas(self):
        resultados = buscar("cross-validation", self.corpus, modo="Lexical (sem API)")
        _, fontes = montar_contexto(resultados)
        base = {"titulo": "Teste", "slides": [{"template_id": "pixel_conceito", "campos": {"titulo": "Teste", "conteudo": "Teste [E99]"}}]}
        with self.assertRaisesRegex(ValueError, "evidências válidas"):
            validar_slides(copy.deepcopy(base), fontes, "pixel", 4, "")
        base["slides"][0]["campos"]["conteudo"] = "Sem citação"
        with self.assertRaises(ValueError):
            validar_slides(copy.deepcopy(base), fontes, "pixel", 4, "")
        formula = {"titulo": "Teste", "slides": [{"template_id": "pixel_formula", "campos": {
            "titulo": "Teste", "conteudo": "Explicação [E1]", "formula": "#read(\"arquivo\")", "legenda": "[E1]",
        }}]}
        with self.assertRaisesRegex(ValueError, "matemática Typst"):
            validar_slides(formula, fontes, "pixel", 4, "")

    def test_geracao_simulada_tem_referencias_e_esquema(self):
        resultados = buscar("cross-validation", self.corpus, modo="Lexical (sem API)")
        cliente = MagicMock()
        cliente.models.generate_content.return_value = SimpleNamespace(text=json.dumps({
            "titulo": "Validação cruzada", "slides": [{"template_id": "pixel_conceito", "campos": {
                "titulo": "Validação cruzada", "conteudo": "A validação cruzada estima o erro de teste. [E1]",
            }}],
        }))
        with patch("rag_web.cliente_gemini") as fabrica:
            fabrica.return_value.__enter__.return_value = cliente
            dados, fontes = gerar_slides("Explique cross-validation", resultados, chave="teste", modelo="modelo-teste")
        self.assertIn("ISLP-5.pdf", dados["slides"][0]["campos"]["fontes"])
        self.assertEqual(len(fontes), 3)
        parametros = cliente.models.generate_content.call_args.kwargs
        self.assertEqual(parametros["model"], "modelo-teste")
        self.assertEqual(parametros["config"].response_mime_type, "application/json")
        self.assertTrue(parametros["config"].response_json_schema)

    def test_pdf_real_nos_dois_temas_sem_sobrescrever_output(self):
        pasta = RAIZ / "templates_typst_v2/output"
        antes = {p.name: p.stat().st_mtime_ns for p in pasta.iterdir() if p.is_file()}
        dados = json.loads((RAIZ / "templates_typst_v2/conteudo.json").read_text())
        for tema in ("pixel", "ufabc"):
            pdf = compilar_pdf(dados, tema)
            self.assertTrue(pdf.startswith(b"%PDF"))
            self.assertGreater(len(pdf), 10_000)
        depois = {p.name: p.stat().st_mtime_ns for p in pasta.iterdir() if p.is_file()}
        self.assertEqual(antes, depois)

    def test_cliente_tem_timeout_sem_repeticoes_automaticas(self):
        with patch("rag_web.genai.Client") as fabrica:
            cliente_gemini("teste")
        opcoes = fabrica.call_args.kwargs["http_options"]
        self.assertEqual(opcoes.timeout, 90_000)
        self.assertEqual(opcoes.retry_options.attempts, 1)

    def test_erros_de_quota_nao_expoem_resposta_da_api(self):
        erro = RuntimeError("corpo confidencial")
        erro.code = 429
        self.assertIn("cota", mensagem_erro(erro))
        self.assertNotIn("confidencial", mensagem_erro(erro))


class InterfaceTest(unittest.TestCase):
    def iniciar(self):
        from streamlit.testing.v1 import AppTest
        return AppTest.from_file(str(RAIZ / "streamlit_app.py"), default_timeout=30)

    def test_consulta_lexical_abre_evidencias_e_limpa_resultados_anteriores(self):
        from web_conteudo import PERGUNTAS_SUGERIDAS

        app = self.iniciar().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.selectbox(key="modo_busca").value, "Lexical (sem API)")
        self.assertEqual(tuple(app.selectbox(key="pergunta").options), PERGUNTAS_SUGERIDAS)
        self.assertFalse(any("chave" in campo.label.lower() for campo in app.text_input))
        self.assertEqual(app.button[0].label, "Buscar no livro")
        app.selectbox(key="pergunta").select(PERGUNTAS_SUGERIDAS[0])
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertTrue(app.session_state["consulta_atual"]["resultados"])
        painel = next(e for e in app.expander if e.label == "Consultar as evidências encontradas")
        self.assertTrue(painel.proto.expanded)
        self.assertTrue(any("149 chunkings" == e.value for e in app.caption))
        self.assertEqual(app.slider[0].label, "Número de páginas")
        self.assertEqual(app.text_input[0].label, "Título")
        app.selectbox(key="pergunta").set_value(None)
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertNotIn("consulta_atual", app.session_state)
        self.assertNotIn("link_apresentacao", app.session_state)

    def test_exemplos_sao_links_e_abrem_sem_chamar_o_gemini(self):
        from web_conteudo import EXEMPLOS

        app = self.iniciar().run()
        links = [e.proto for e in app.get("link_button") if e.proto.label == "Ver apresentação"]
        diretos = [e.proto for e in app.get("link_button") if e.proto.label == "PDF direto"]
        self.assertEqual(len(links), 3)
        self.assertEqual(len(diretos), 0)
        for exemplo in EXEMPLOS:
            self.assertTrue(any(f"/app/static/apresentacoes/{exemplo['arquivo']}" in link.url and link.type == "primary" for link in links))
            pagina = self.iniciar()
            pagina.query_params["exemplo"] = exemplo["id"]
            with patch("rag_web.cliente_gemini", side_effect=AssertionError("API inesperada")):
                pagina.run()
            self.assertFalse(pagina.exception)
            self.assertFalse(pagina.subheader)
            self.assertFalse(pagina.selectbox)
            self.assertTrue(any(exemplo["arquivo"] in e.proto.url for e in pagina.get("link_button")))
            self.assertTrue((RAIZ / "static/apresentacoes" / exemplo["arquivo"]).read_bytes().startswith(b"%PDF"))

    def test_chave_do_servidor_e_usada_sem_campo_para_visitante(self):
        from web_conteudo import PERGUNTAS_SUGERIDAS

        with patch.dict("os.environ", {"GEMINI_API_KEY": "chave-simulada"}):
            app = self.iniciar().run()
            self.assertEqual(app.selectbox(key="modo_busca").value, "Híbrida")
            self.assertFalse(any("chave" in campo.label.lower() for campo in app.text_input))
            app.selectbox(key="pergunta").select(PERGUNTAS_SUGERIDAS[1])
            with patch("rag_web.buscar", return_value=[]) as consulta:
                app.button[0].click().run()
            self.assertFalse(app.exception)
            self.assertEqual(consulta.call_args.kwargs["chave"], "chave-simulada")

    def test_gera_na_mesma_pagina_e_oferece_pdf_direto_sem_repetir_chamada(self):
        from web_conteudo import PERGUNTAS_SUGERIDAS

        resultados = buscar("cross-validation", carregar_corpus(), modo="Lexical (sem API)")
        with patch.dict("os.environ", {"GEMINI_API_KEY": "chave-simulada"}):
            app = self.iniciar().run()
            app.selectbox(key="pergunta").select(PERGUNTAS_SUGERIDAS[0])
            with patch("rag_web.buscar", return_value=resultados):
                app.button[0].click().run()
            app.text_input[0].set_value("Minha apresentação").run()
            app.slider[0].set_value(5).run()
            token = app.session_state["link_apresentacao"]["token"]
            self.assertTrue(any(e.label == "Gerar apresentação" for e in app.button))
            self.assertFalse(any(e.proto.label == "Gerar apresentação" for e in app.get("link_button")))
            self.assertFalse(any("Conteúdo e referências" in e.label for e in app.expander))
            dados = {"titulo": "Gerado", "slides": [{"template_id": "pixel_abertura", "campos": {"titulo": "Gerado"}}]}
            with TemporaryDirectory() as pasta:
                with patch("web_apresentacoes.PASTA_PDFS", Path(pasta)):
                    with patch("rag_web.gerar_slides", return_value=(dados, [])) as gerar:
                        with patch("rag_web.compilar_pdf", return_value=b"%PDF-simulado") as compilar:
                            next(b for b in app.button if b.label == "Gerar apresentação").click().run()
                            app.run()
                    self.assertEqual((Path(pasta) / f"{token}.pdf").read_bytes(), b"%PDF-simulado")
                    self.assertTrue(any(f"/app/static/geradas/{token}.pdf" in e.proto.url for e in app.get("link_button")))
            self.assertFalse(app.exception)
            self.assertTrue(app.success)
            self.assertFalse(app.query_params)
            self.assertTrue(app.selectbox)
            self.assertFalse(any(b.label == "Gerar apresentação" for b in app.button))
            self.assertEqual(gerar.call_count, 1)
            self.assertEqual(gerar.call_args.kwargs["modelo"], "gemini-3.6-flash")
            self.assertEqual(gerar.call_args.kwargs["quantidade"], 5)
            self.assertEqual(compilar.call_args.args[0]["titulo"], "Minha apresentação")
            self.assertEqual(compilar.call_args.args[0]["slides"][0]["campos"]["titulo"], "Minha apresentação")

    def test_link_invalido_nao_chama_api(self):
        pagina = self.iniciar()
        pagina.query_params["apresentacao"] = "inexistente"
        with patch("rag_web.cliente_gemini", side_effect=AssertionError("API inesperada")):
            pagina.run()
        self.assertFalse(pagina.exception)
        self.assertTrue(pagina.info)

    def test_falha_na_geracao_mantem_consulta_e_permite_tentar_novamente(self):
        from web_conteudo import PERGUNTAS_SUGERIDAS

        resultados = buscar("cross-validation", carregar_corpus(), modo="Lexical (sem API)")
        with patch.dict("os.environ", {"GEMINI_API_KEY": "chave-simulada"}):
            app = self.iniciar().run()
            app.selectbox(key="pergunta").select(PERGUNTAS_SUGERIDAS[0])
            with patch("rag_web.buscar", return_value=resultados):
                app.button[0].click().run()
            token = app.session_state["link_apresentacao"]["token"]
            with patch("rag_web.gerar_slides", side_effect=RuntimeError("Falha simulada")):
                next(b for b in app.button if b.label == "Gerar apresentação").click().run()
            self.assertFalse(app.exception)
            self.assertTrue(app.error)
            self.assertTrue(app.session_state["consulta_atual"])
            self.assertEqual(app.session_state["link_apresentacao"]["token"], token)
            self.assertTrue(any(b.label == "Gerar apresentação" for b in app.button))
            self.assertFalse(any("/geradas/" in e.proto.url for e in app.get("link_button")))

    def test_links_publicos_usam_arquivos_sem_interface_do_streamlit(self):
        app = self.iniciar()
        app.context["url"] = "https://stats-rag.streamlit.app/"
        app.run()
        self.assertFalse(app.exception)
        links = [e.proto for e in app.get("link_button")]
        self.assertEqual(len(links), 3)
        self.assertTrue(all(e.url.startswith("https://stats-rag.streamlit.app/~/+/app/static/") for e in links))


class CatalogoTest(unittest.TestCase):
    def dados(self, pergunta):
        return dict(pergunta=pergunta, resultados=[], tema="pixel", quantidade=4, titulo="")

    def test_tokens_separam_visitantes_e_limite_remove_o_mais_antigo(self):
        from web_apresentacoes import CatalogoApresentacoes

        catalogo = CatalogoApresentacoes(limite=2)
        primeiro = catalogo.adicionar(**self.dados("Pergunta de A"))
        segundo = catalogo.adicionar(**self.dados("Pergunta de B"))
        self.assertNotEqual(primeiro, segundo)
        self.assertEqual(catalogo.obter(primeiro).pergunta, "Pergunta de A")
        terceiro = catalogo.adicionar(**self.dados("Pergunta de C"))
        self.assertIsNone(catalogo.obter(primeiro))
        self.assertEqual(catalogo.obter(segundo).pergunta, "Pergunta de B")
        self.assertIsNotNone(catalogo.obter(terceiro))

    def test_pedidos_expiram(self):
        from web_apresentacoes import CatalogoApresentacoes, salvar_pdf

        catalogo = CatalogoApresentacoes(duracao=60)
        token = catalogo.adicionar(**self.dados("Teste"))
        pedido = catalogo.obter(token)
        with TemporaryDirectory() as pasta:
            with patch("web_apresentacoes.PASTA_PDFS", Path(pasta)):
                salvar_pdf(token, b"%PDF-teste")
                pedido.criado_em -= 61
                self.assertIsNone(catalogo.obter(token))
                self.assertFalse((Path(pasta) / f"{token}.pdf").exists())

    def test_salvar_pdf_rejeita_caminho_fora_da_pasta(self):
        from web_apresentacoes import salvar_pdf

        with self.assertRaises(ValueError):
            salvar_pdf("../arquivo", b"%PDF-teste")


if __name__ == "__main__":
    unittest.main()
