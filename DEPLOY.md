# Stats RAG na web

Aplicativo publicado: <https://stats-rag.streamlit.app/>.

O aplicativo usa **Streamlit Community Cloud** para servir a interface e executar
as consultas em Python no servidor. A hospedagem é gratuita; o Gemini depende da
cota disponível na chave configurada. Não é necessário contratar Elasticsearch,
banco vetorial ou outra hospedagem para o backend.

## Publicar

1. Envie estes arquivos ao repositório `lucasarauj0h/stats-rag` no GitHub.
2. Entre em <https://share.streamlit.io/> com sua conta e conecte o GitHub.
3. Crie um aplicativo com repositório `lucasarauj0h/stats-rag`, branch `main`
   e arquivo de entrada `streamlit_app.py`.
4. Em **Advanced settings**, selecione **Python 3.12**. Se quiser disponibilizar
   uma chave compartilhada, configure `GEMINI_API_KEY` no campo **Secrets**.
   A chave é usada exclusivamente no servidor; os visitantes não precisam informá-la.
   Sem a configuração, a busca lexical e os exemplos prontos continuam disponíveis.
   O modelo de geração da aplicação web é `gemini-3.6-flash`, definido em
   `web_conteudo.py`. A configuração do notebook é independente.
5. Clique em **Deploy**. A hospedagem fornece um endereço `*.streamlit.app`.

Não envie `.env` nem `.streamlit/secrets.toml` ao GitHub. O arquivo
`.streamlit/secrets.toml.example` mostra somente nomes e exemplos de configuração.
Uma chave compartilhada consome a cota do responsável por todas as consultas dos
visitantes. O aplicativo não transforma uma API paga em gratuita nem aumenta cotas.

## Dados e processamento

O deploy recebe os arquivos versionados no GitHub. O servidor carrega o manifesto,
os chunks e os vetores da pasta `artifacts/`, verifica seus hashes e reutiliza o
índice. Atualmente são 149 chunks dos capítulos 5, 7 e 8 do ISLP. Os PDFs em
`corpus/` ficam disponíveis para download junto das evidências.

Cada busca híbrida gera apenas o embedding da pergunta, usando exatamente o modelo,
a dimensão e o formato do manifesto. BM25, cosseno e RRF rodam no servidor. O usuário
pode inspecionar os trechos, gerar slides com as três primeiras evidências e baixar
PDF, JSON e referências. A compilação Typst usa arquivos temporários separados por
operação; resultados não são gravados nos artefatos.

O campo da pergunta oferece oito sugestões e aceita perguntas livres. Depois da
consulta, as evidências são expandidas automaticamente. Tema, número de páginas e
título ficam em três colunas. Os botões de apresentação abrem uma nova guia com
o leitor PDF, sem exibir o JSON ou o conteúdo dos slides na página da consulta.
Os exemplos em `exemplos/` abrem sem chamadas ao Gemini.

Os pedidos de geração ficam em um catálogo temporário em memória, limitado a 32
apresentações por uma hora. A guia nova recupera o pedido por um identificador
aleatório; perguntas, evidências e credenciais não são colocadas na URL. Reabrir
um PDF já gerado reutiliza o resultado. Links gerados expiram após uma hora ou ao
reiniciar o servidor; os exemplos permanecem disponíveis. Baixe o PDF para guardá-lo.

Mantenha extração, atualização do corpus e geração dos embeddings no notebook.
Quando atualizar o índice, publique juntos o manifesto, chunks e vetores. Não é
necessário mover os dados para outro serviço neste tamanho de corpus.

O disco da hospedagem não deve ser usado como armazenamento permanente. O aplicativo
pode hibernar ou reiniciar, e resultados de uma sessão podem ser perdidos. Os downloads
permitem guardar as apresentações. Alterações enviadas ao GitHub atualizam o aplicativo.

## Executar e verificar localmente

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Para os testes locais:

```bash
python -m unittest discover -s tests -v
```

Os testes verificam o índice real, a busca lexical, o contrato da busca híbrida,
a interface, validação de citações e compilação real de PDFs nos dois temas.
Chamadas ao Gemini são simuladas: esses testes não comprovam acesso, disponibilidade
do modelo, cota ou qualidade da geração ao vivo. Após o deploy, faça uma consulta
híbrida e gere um PDF com uma chave válida para verificar a integração completa.

Referências: [Streamlit Community Cloud](https://docs.streamlit.io/deploy/streamlit-community-cloud),
[publicação](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy)
e [segredos](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management).
