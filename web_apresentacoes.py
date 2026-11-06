"""Pedidos temporários para abrir apresentações em outra sessão do navegador."""

from dataclasses import dataclass, field
from pathlib import Path
from secrets import token_urlsafe
from threading import Lock
from time import monotonic

PASTA_PDFS = Path(__file__).resolve().parent / "static" / "geradas"


def salvar_pdf(token, pdf):
    """Publica somente o PDF final em um endereço aleatório, sem credenciais."""
    if not token or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in token):
        raise ValueError("Identificador de apresentação inválido.")
    PASTA_PDFS.mkdir(parents=True, exist_ok=True)
    temporario = PASTA_PDFS / f"{token}.tmp"
    temporario.write_bytes(pdf)
    temporario.replace(PASTA_PDFS / f"{token}.pdf")


def remover_pdf(token):
    (PASTA_PDFS / f"{token}.pdf").unlink(missing_ok=True)


@dataclass
class PedidoApresentacao:
    pergunta: str
    resultados: list
    tema: str
    quantidade: int
    titulo: str
    criado_em: float = field(default_factory=monotonic)
    pdf: bytes | None = None
    bloqueio: Lock = field(default_factory=Lock, repr=False)


class CatalogoApresentacoes:
    """Compartilha apenas pedidos opacos e PDFs; nenhuma chave entra no catálogo."""

    def __init__(self, duracao=3600, limite=32):
        self.duracao = duracao
        self.limite = limite
        self._pedidos = {}
        self._bloqueio = Lock()

    def _limpar(self):
        agora = monotonic()
        expirados = [token for token, pedido in self._pedidos.items() if agora - pedido.criado_em >= self.duracao]
        for token in expirados:
            remover_pdf(token)
            del self._pedidos[token]

    def adicionar(self, **dados):
        pedido = PedidoApresentacao(**dados)
        with self._bloqueio:
            self._limpar()
            if len(self._pedidos) >= self.limite:
                antigo = min(self._pedidos, key=lambda token: self._pedidos[token].criado_em)
                remover_pdf(antigo)
                del self._pedidos[antigo]
            token = token_urlsafe(32)
            self._pedidos[token] = pedido
        return token

    def obter(self, token):
        with self._bloqueio:
            self._limpar()
            return self._pedidos.get(token)
