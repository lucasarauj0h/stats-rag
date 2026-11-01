// Entrada do documento. O conteúdo pode vir do JSON ou do Python no Colab.
#import "temas.typ": renderizar

#let dados = if "conteudo" in sys.inputs {
  json(bytes(sys.inputs.conteudo))
} else {
  json("conteudo.json")
}

#let estruturas = json("estruturas.json")
#set document(
  title: dados.at("titulo", default: "Estatística com RAG"),
  author: dados.at("autor", default: ""),
)

#renderizar(dados, estruturas)
