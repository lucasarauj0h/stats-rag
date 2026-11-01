// Versão 2: títulos compactos, corpo de texto livre e tipografia Pixelify Sans.
#let u = 0.75pt
#let largura = 1280 * u
#let altura = 720 * u
#let marinho = rgb("09121F")
#let verde = rgb("005C3C")
#let menta = rgb("86F6CD")
#let dois(n) = if n < 10 { "0" + str(n) } else { str(n) }
#let em(x, y, corpo) = place(top + left, dx: x * u, dy: y * u, corpo)

#let imagem(nome, x: 0, y: 0, w: 1280, h: 720, pixel: false) = em(x, y,
  image("assets/" + nome, width: w * u, height: h * u, fit: "cover",
    scaling: if pixel { "pixelated" } else { "smooth" },
    alt: if pixel { "Fundo decorativo pixelado de ciência de dados" }
      else { "Campus da UFABC, fotografia do portal institucional" },
  )
)

#let superficie(cor, x: 0, y: 0, w: 1280, h: 720) = em(x, y,
  rect(width: w * u, height: h * u, fill: cor, stroke: none)
)

#let logo(negativo: false, x: 1054, y: 40, w: 160) = {
  let arquivo = if negativo { "negativo_logotipo-ufabc-lateral.png" }
    else { "principal_logotipo-ufabc-lateral.png" }
  let topo = if negativo { 117 } else { 178 }
  let h-original = if negativo { 482 } else { 612 }
  em(x, y, box(width: w * u, height: w * 211 / 663 * u, clip: true,
    place(top + left, dx: -w * 65 / 663 * u, dy: -w * topo / 663 * u,
      image("assets/" + arquivo, width: w * 792 / 663 * u,
        height: w * h-original / 663 * u,
        alt: "Logotipo oficial da Universidade Federal do ABC",
      )
    )
  ))
}

#let texto-simples(valor) = {
  for (p, paragrafo) in valor.split("\n\n").enumerate() {
    if p > 0 { parbreak() }
    for (i, linha) in paragrafo.split("\n").enumerate() {
      if i > 0 { linebreak() }
      text(linha)
    }
  }
}

#let conteudo-campo(valor, campo, tamanho) = {
  set text(font: campo.fonte, size: tamanho * 1pt,
    fill: rgb(campo.cor), weight: if campo.negrito { "bold" } else { "regular" },
    lang: "pt", hyphenate: false,
  )
  set par(leading: if campo.fonte == "Pixelify Sans" { 0.38em } else { 0.30em },
    spacing: 0.65em, justify: false,
  )
  if campo.papel == "formula" {
    assert(not valor.contains("#") and not valor.contains("$"),
      message: "Use uma expressão matemática Typst, sem # ou $.")
    math.equation(block: false, math.display(eval(valor, mode: "math")))
  } else {
    texto-simples(valor)
  }
}

#let campo-fixo(layout-id, campo, valor) = context {
  let caixa = campo.caixa_px
  let w = caixa.largura * u
  let h = caixa.altura * u
  let base = campo.tamanho_pt
  let minimo = campo.minimo_pt
  let passos = int(calc.floor((base - minimo) * 2))
  let escolhido = none
  let corpo = none
  for passo in range(passos + 1) {
    if escolhido == none {
      let tamanho = base - passo * 0.5
      let candidato = conteudo-campo(valor, campo, tamanho)
      let m = measure(candidato, width: w)
      if m.width <= w + 0.1pt and m.height <= h + 0.1pt {
        escolhido = tamanho
        corpo = candidato
      }
    }
  }
  assert(escolhido != none,
    message: "O campo '" + campo.nome + "' do template '" + layout-id
      + "' não cabe na fonte mínima. Resuma o texto ou divida em outro slide.")
  em(caixa.x, caixa.y, [
    #metadata((template: layout-id, campo: campo.nome,
      fonte: campo.fonte, fonte_base_pt: base, fonte_usada_pt: escolhido,
      largura_px: caixa.largura, altura_px: caixa.altura,
    )) <encaixe>
    #block(width: w, height: h, breakable: false, corpo)
  ])
}

#let fundo(id) = {
  if id.starts-with("pixel_") {
    imagem(id + ".png", pixel: true)
  } else if id == "ufabc_abertura" {
    imagem("campus_sa.jpg")
    superficie(rgb("003A29").transparentize(10%))
    logo(negativo: true)
  } else if id == "ufabc_conceito" {
    imagem("campus_sbc.jpg", y: 622, h: 98)
    superficie(rgb("FCFCF8").transparentize(12%), y: 622, h: 98)
    logo()
  } else if id == "ufabc_comparacao" {
    imagem("campus_sa.jpg", h: 130)
    superficie(rgb("003A29").transparentize(10%), h: 130)
    logo(negativo: true)
  } else if id == "ufabc_formula" {
    imagem("campus_sbc.jpg")
    superficie(rgb("FCFCF8").transparentize(4%))
    logo()
  }
}

#let renderizar(dados, estruturas) = {
  let lista = dados.slides
  assert(lista.len() > 0, message: "Inclua pelo menos um slide.")
  for (i, slide) in lista.enumerate() {
    let encontrados = estruturas.layouts.filter(l => l.template_id == slide.template_id)
    assert(encontrados.len() == 1, message: "Template desconhecido: " + slide.template_id)
    let layout = encontrados.first()
    let id = layout.template_id
    let pixel = layout.tema == "pixel"
    let escuro = pixel or id == "ufabc_abertura"
    page(width: largura, height: altura, margin: 0pt,
      fill: if escuro { marinho } else { rgb("FCFCF8") },
      background: none, foreground: none, header: none, footer: none, numbering: none,
    )[
      #fundo(id)
      #for campo in layout.campos {
        campo-fixo(id, campo, slide.campos.at(campo.nome, default: ""))
      }
      #em(1144, 670, {
        set text(font: if pixel { "Pixelify Sans" } else { "Fira Sans" },
          size: 10.5pt, fill: if escuro { menta } else { verde })
        box(width: 95 * u, dois(i + 1) + " / " + dois(lista.len()))
      })
    ]
  }
}
