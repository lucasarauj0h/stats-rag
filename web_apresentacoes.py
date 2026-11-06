"""Pedidos temporários para abrir apresentações em outra sessão do navegador."""

from dataclasses import dataclass, field
from secrets import token_urlsafe
from threading import Lock
from time import monotonic


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
        self._pedidos = {
            token: pedido for token, pedido in self._pedidos.items()
            if agora - pedido.criado_em < self.duracao
        }

    def adicionar(self, **dados):
        pedido = PedidoApresentacao(**dados)
        with self._bloqueio:
            self._limpar()
            if len(self._pedidos) >= self.limite:
                antigo = min(self._pedidos, key=lambda token: self._pedidos[token].criado_em)
                del self._pedidos[antigo]
            token = token_urlsafe(32)
            self._pedidos[token] = pedido
        return token

    def obter(self, token):
        with self._bloqueio:
            self._limpar()
            return self._pedidos.get(token)
