# Artefatos do RAG

Os arquivos nesta pasta permitem retomar a busca sem gerar novamente os embeddings.

- `manifest.json`: configuração, quantidade de chunks e SHA-256 dos PDFs e artefatos.
- `documentos/ISLP-*/chunks.jsonl`: texto e metadados de cada chunk, incluindo páginas e seções.
- `embeddings/<configuração>/ISLP-*.npz`: matriz NumPy `float32`, normalizada em L2, com os identificadores e hashes correspondentes.

Cada PDF é salvo separadamente assim que termina. O notebook reúne os capítulos em um único índice em memória.
Antes de chamar a API, ele procura vetores locais e, se necessário, os publicados no GitHub.
O reuso depende do hash do texto enviado e da configuração completa do embedding: só os textos faltantes ou alterados são enviados.
Mudar a pergunta reutiliza os embeddings dos documentos. A pergunta tem seu próprio embedding, reutilizado entre as duas buscas na mesma sessão.

Para disponibilizar o cache no Colab, publique **esta pasta inteira e `rag_artefatos.py` na raiz do repositório**, além de `corpus/` e `templates_typst_v2/`.
O Colab baixa os arquivos do repositório e grava atualizações em `/content/stats-rag/artifacts/`.
Baixe ou publique essas atualizações antes de encerrar a sessão, pois `/content` é temporário.
As novas execuções não fazem upload automático para o GitHub.

O JSONL é texto UTF-8; o NPZ é lido com `allow_pickle=False`. Os hashes detectam arquivos alterados, e a configuração impede a mistura de vetores incompatíveis.
Credenciais não fazem parte destes artefatos; a API key é informada durante a execução ou pela variável de ambiente `GEMINI_API_KEY`.
