"""Validação local sem chamadas pagas: índice real, respostas simuladas e PDF real."""

import copy
import json
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
    def test_consulta_lexical_e_limpeza_dos_resultados_anteriores(self):
        from streamlit.testing.v1 import AppTest

        app = AppTest.from_file(str(RAIZ / "streamlit_app.py"), default_timeout=30).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.selectbox[0].value, "Lexical (sem API)")
        app.text_area[0].set_value("cross-validation LOOCV")
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertTrue(app.session_state["consulta_atual"]["resultados"])
        app.session_state["apresentacao"] = {"dados": {"titulo": "Antiga", "slides": []}}
        app.text_area[0].set_value("zzzzzzzzzzxyz")
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertFalse(app.session_state["consulta_atual"]["resultados"])
        self.assertNotIn("apresentacao", app.session_state)


if __name__ == "__main__":
    unittest.main()
