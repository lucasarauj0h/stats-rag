"""Persistência incremental dos chunks e embeddings, localmente ou no GitHub."""
from collections import Counter
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path, PurePosixPath
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

import numpy as np


def hash_texto(texto):
    return sha256(texto.encode("utf-8")).hexdigest()


def hash_arquivo(caminho):
    return sha256(Path(caminho).read_bytes()).hexdigest()


def _json(dados):
    return json.dumps(dados, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _gravar(caminho, conteudo):
    caminho = Path(caminho)
    if caminho.is_file() and caminho.read_bytes() == conteudo:
        return False
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_name(caminho.name + ".tmp")
    temporario.write_bytes(conteudo)
    temporario.replace(caminho)
    return True


class ArtefatosRAG:
    def __init__(self, raiz, documentos, repositorio=None, branch="main"):
        self.raiz = Path(raiz).resolve()
        self.documentos = tuple(documentos)
        self.repositorio = repositorio
        self.branch = branch
        self.manifesto = self.raiz / "artifacts" / "manifest.json"
        self._manifesto_remoto = None
        self._remoto_consultado = False

    def _caminho(self, relativo):
        caminho = self.raiz / PurePosixPath(relativo)
        if not caminho.resolve().is_relative_to(self.raiz / "artifacts"):
            raise ValueError("Caminho de artefato fora da pasta artifacts.")
        return caminho

    def _chave_config(self, config):
        return hash_texto(json.dumps(config, sort_keys=True))[:20]

    def _arquivos(self, nome, config):
        if Path(nome).name != nome or nome not in self.documentos:
            raise ValueError("Documento fora do corpus configurado.")
        stem = Path(nome).stem
        chave = self._chave_config(config)
        return (
            self.raiz / "artifacts" / "documentos" / stem / "chunks.jsonl",
            self.raiz / "artifacts" / "embeddings" / chave / f"{stem}.npz",
        )

    def _consultar_remoto(self):
        if self._remoto_consultado or not self.repositorio:
            return self._manifesto_remoto
        self._remoto_consultado = True
        url = (f"https://raw.githubusercontent.com/{self.repositorio}/"
               f"{self.branch}/artifacts/manifest.json")
        try:
            with urlopen(url, timeout=30) as resposta:
                dados = json.load(resposta)
            if dados.get("versao_arquivo") != 1:
                raise ValueError("Versão desconhecida do manifesto remoto.")
            self._manifesto_remoto = dados
        except HTTPError as erro:
            if erro.code != 404:
                raise
            print("GitHub: ainda não há artefatos publicados; usando o cache local.")
        except (URLError, TimeoutError) as erro:
            print(f"GitHub indisponível ({type(erro).__name__}); usando o cache local.")
        return self._manifesto_remoto

    def _baixar_documento(self, nome, config):
        manifesto = self._consultar_remoto()
        if not manifesto or manifesto.get("config_embeddings") != config:
            return False
        documento = manifesto.get("documentos", {}).get(nome)
        if not documento:
            return False
        for campo in ("chunks", "embeddings"):
            registro = documento[campo]
            destino = self._caminho(registro["path"])
            if destino.is_file() and hash_arquivo(destino) == registro["sha256"]:
                continue
            url = (f"https://raw.githubusercontent.com/{self.repositorio}/"
                   f"{self.branch}/{registro['path']}")
            with urlopen(url, timeout=60) as resposta:
                conteudo = resposta.read()
            if sha256(conteudo).hexdigest() != registro["sha256"]:
                raise ValueError(f"Hash inválido no artefato remoto de {nome}.")
            _gravar(destino, conteudo)
        print("Artefatos recuperados do GitHub:", nome)
        return True

    def _ler_vetores(self, caminho, config):
        with np.load(caminho, allow_pickle=False) as pacote:
            matriz = pacote["matriz"].copy()
            dados = json.loads(pacote["dados_json"].item())
        if dados.get("versao_arquivo") != 1 or dados.get("config") != config:
            raise ValueError("Configuração incompatível no cache de embeddings.")
        hashes = dados["embedding_hashes"]
        if (matriz.shape != (len(hashes), config["dimensao"])
                or len(dados["chunk_ids"]) != len(hashes)
                or len(dados["content_hashes"]) != len(hashes)):
            raise ValueError("Metadados e matriz do cache não correspondem.")
        if (matriz.dtype != np.float32 or not np.isfinite(matriz).all()
                or not np.allclose(np.linalg.norm(matriz, axis=1), 1.0, atol=1e-5)):
            raise ValueError("Vetores inválidos ou sem normalização L2.")
        return matriz, dados

    def restaurar_embeddings(self, chunks, config, cache):
        disponiveis = {}
        for nome in self.documentos:
            _, caminho = self._arquivos(nome, config)
            if not caminho.is_file():
                self._baixar_documento(nome, config)
            if not caminho.is_file():
                continue
            try:
                matriz, dados = self._ler_vetores(caminho, config)
            except (ValueError, KeyError, OSError) as erro:
                print(f"Cache inválido de {nome}; será reconstruído ({type(erro).__name__}).")
                continue
            for chave, vetor in zip(dados["embedding_hashes"], matriz):
                disponiveis[chave] = vetor

        reutilizados = 0
        for chunk in chunks:
            texto = config["formato_documento"].format(content=chunk["content"])
            chave = hash_texto(texto)
            if chave in disponiveis:
                cache[(config["modelo"], config["dimensao"],
                       "texto_formatado_l2_float32_v1", chave)] = disponiveis[chave].copy()
                reutilizados += 1
        print(f"Embeddings reutilizados dos artefatos: {reutilizados}/{len(chunks)}")
        print("Chunks ainda sem embedding salvo:", len(chunks) - reutilizados)
        return reutilizados

    def estabilizar_metadados(self, chunks, config):
        for nome in self.documentos:
            caminho, _ = self._arquivos(nome, config)
            if not caminho.is_file():
                continue
            antigos = {}
            for linha in caminho.read_text(encoding="utf-8").splitlines():
                trecho = json.loads(linha)
                antigos[(trecho["chunk_id"], hash_texto(trecho["content"]))] = trecho
            for trecho in chunks:
                if trecho["source"] == nome:
                    anterior = antigos.get((trecho["chunk_id"], hash_texto(trecho["content"])))
                    if anterior:
                        trecho["created_at"] = anterior["created_at"]

    def salvar_documentos(self, chunks, indice, config_chunking=None, permitir_parcial=False):
        config = indice["config"]
        matriz = np.asarray(indice["matriz"])
        ids = [c["chunk_id"] for c in chunks]
        hashes = [hash_texto(c["content"]) for c in chunks]
        if (ids != list(indice["chunk_ids"])
                or hashes != list(indice["content_hashes"])
                or len(set(ids)) != len(ids)
                or matriz.shape != (len(chunks), config["dimensao"])):
            raise ValueError("Os chunks e os embeddings não correspondem.")
        if (matriz.dtype != np.float32 or not np.isfinite(matriz).all()
                or not np.allclose(np.linalg.norm(matriz, axis=1), 1, atol=1e-5)):
            raise ValueError("A matriz de embeddings não é válida.")
        presentes = set(c["source"] for c in chunks)
        if (not presentes <= set(self.documentos)
                or (not permitir_parcial and presentes != set(self.documentos))):
            raise ValueError("O índice não contém todos os PDFs configurados.")
        self.estabilizar_metadados(chunks, config)
        documentos = {}
        if permitir_parcial and self.manifesto.is_file():
            anterior = json.loads(self.manifesto.read_text(encoding="utf-8"))
            if anterior.get("config_embeddings") == config:
                documentos = anterior.get("documentos", {}).copy()
        for nome in self.documentos:
            if nome not in presentes:
                continue
            posicoes = [i for i, c in enumerate(chunks) if c["source"] == nome]
            lista = [dict(chunks[i], file_path=f"corpus/{nome}") for i in posicoes]
            caminho_chunks, caminho_vetores = self._arquivos(nome, config)
            texto = "".join(json.dumps(c, ensure_ascii=False, sort_keys=True) + "\n"
                            for c in lista)
            mudou_chunks = _gravar(caminho_chunks, texto.encode("utf-8"))
            dados = {
                "versao_arquivo": 1, "config": config,
                "chunk_ids": [c["chunk_id"] for c in lista],
                "content_hashes": [hash_texto(c["content"]) for c in lista],
                "embedding_hashes": [hash_texto(config["formato_documento"].format(
                    content=c["content"])) for c in lista],
            }
            matriz_doc = matriz[posicoes]
            igual = False
            if caminho_vetores.is_file():
                try:
                    anterior_matriz, anterior_dados = self._ler_vetores(caminho_vetores, config)
                    igual = anterior_dados == dados and np.array_equal(anterior_matriz, matriz_doc)
                except (ValueError, KeyError, OSError):
                    pass
            if not igual:
                buffer = BytesIO()
                np.savez_compressed(buffer, matriz=matriz_doc,
                                    dados_json=np.array(json.dumps(dados, ensure_ascii=False)))
                _gravar(caminho_vetores, buffer.getvalue())
            documentos[nome] = {
                "pdf_sha256": hash_arquivo(self.raiz / "corpus" / nome),
                "quantidade_chunks": len(lista),
                "chunks": {"path": caminho_chunks.relative_to(self.raiz).as_posix(),
                           "sha256": hash_arquivo(caminho_chunks)},
                "embeddings": {"path": caminho_vetores.relative_to(self.raiz).as_posix(),
                               "sha256": hash_arquivo(caminho_vetores)},
            }
            print(f"{nome}: {len(lista)} chunks; "
                  f"{'atualizado' if mudou_chunks or not igual else 'já salvo, sem alteração'}")
        manifesto = {"versao_arquivo": 1, "config_embeddings": config,
                     "config_chunking": config_chunking or {},
                     "quantidade_chunks": sum(d["quantidade_chunks"] for d in documentos.values()),
                     "documentos": documentos}
        _gravar(self.manifesto, _json(manifesto).encode("utf-8"))
        return self.manifesto

    def carregar_indice(self, caminho=None):
        caminho = Path(caminho or self.manifesto)
        if not caminho.is_file():
            remoto = self._consultar_remoto()
            if not remoto:
                raise FileNotFoundError("Ainda não há índice salvo: execute os embeddings e salve os artefatos.")
            for nome in self.documentos:
                if not self._baixar_documento(nome, remoto["config_embeddings"]):
                    raise ValueError(f"O índice remoto não inclui {nome}.")
            _gravar(caminho, _json(remoto).encode("utf-8"))
        manifesto = json.loads(caminho.read_text(encoding="utf-8"))
        if manifesto.get("versao_arquivo") != 1:
            raise ValueError("Versão de manifesto desconhecida.")
        if not set(self.documentos) <= manifesto["documentos"].keys():
            raise ValueError("O índice salvo não contém todos os PDFs configurados.")
        config = manifesto["config_embeddings"]
        chunks, matrizes = [], []
        for nome in self.documentos:
            documento = manifesto["documentos"][nome]
            pdf = self.raiz / "corpus" / nome
            if pdf.is_file() and hash_arquivo(pdf) != documento["pdf_sha256"]:
                raise ValueError(
                    f"O PDF {nome} mudou: execute a extração e atualize seus artefatos."
                )
            caminhos = []
            for campo in ("chunks", "embeddings"):
                registro = documento[campo]
                arquivo = self._caminho(registro["path"])
                if not arquivo.is_file():
                    self._baixar_documento(nome, config)
                if not arquivo.is_file() or hash_arquivo(arquivo) != registro["sha256"]:
                    raise ValueError(f"Arquivo {campo} ausente ou alterado em {nome}.")
                caminhos.append(arquivo)
            registros = [json.loads(l) for l in caminhos[0].read_text(encoding="utf-8").splitlines() if l]
            matriz, dados = self._ler_vetores(caminhos[1], config)
            if (len(registros) != documento["quantidade_chunks"]
                    or [c["chunk_id"] for c in registros] != dados["chunk_ids"]
                    or [hash_texto(c["content"]) for c in registros] != dados["content_hashes"]
                    or any(c["source"] != nome for c in registros)
                    or [hash_texto(config["formato_documento"].format(content=c["content"]))
                        for c in registros] != dados["embedding_hashes"]):
                raise ValueError(f"Chunks e vetores de {nome} não correspondem.")
            chunks.extend(registros)
            matrizes.append(matriz)
        if len({c["chunk_id"] for c in chunks}) != len(chunks):
            raise ValueError("IDs duplicados no índice salvo.")
        indice = {"matriz": np.vstack(matrizes),
                  "chunk_ids": [c["chunk_id"] for c in chunks],
                  "content_hashes": [hash_texto(c["content"]) for c in chunks],
                  "config": config}
        print("Índice carregado dos artefatos:", dict(Counter(c["source"] for c in chunks)))
        return chunks, indice
