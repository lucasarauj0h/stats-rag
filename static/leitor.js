import { getDocument, GlobalWorkerOptions } from "./vendor/pdfjs/pdf.min.mjs";

GlobalWorkerOptions.workerSrc = new URL("./vendor/pdfjs/pdf.worker.min.mjs", import.meta.url).href;
const canvas = document.querySelector("#slide");
const status = document.querySelector("#status");
const anterior = document.querySelector("#anterior");
const proxima = document.querySelector("#proxima");
let pdf, pagina = 1, sequencia = 0, desenho;

async function renderizar() {
  const atual = ++sequencia;
  desenho?.cancel();
  const slide = await pdf.getPage(pagina);
  if (atual !== sequencia) return;
  const base = slide.getViewport({ scale: 1 });
  const cabecalho = document.querySelector("header").getBoundingClientRect().height;
  const escala = Math.max(.1, Math.min((innerWidth - 24) / base.width, (innerHeight - cabecalho - 30) / base.height));
  const viewport = slide.getViewport({ scale: escala });
  const proporcao = Math.min(devicePixelRatio || 1, 2);
  canvas.width = Math.floor(viewport.width * proporcao);
  canvas.height = Math.floor(viewport.height * proporcao);
  canvas.style.width = `${viewport.width}px`;
  canvas.style.height = `${viewport.height}px`;
  canvas.hidden = false;
  status.hidden = true;
  canvas.setAttribute("aria-label", `Página ${pagina} de ${pdf.numPages}`);
  document.querySelector("#paginas").textContent = `${pagina} / ${pdf.numPages}`;
  anterior.disabled = pagina === 1;
  proxima.disabled = pagina === pdf.numPages;
  desenho = slide.render({ canvasContext: canvas.getContext("2d"), viewport, transform: [proporcao, 0, 0, proporcao, 0, 0] });
  try { await desenho.promise; }
  catch (erro) { if (erro.name !== "RenderingCancelledException") throw erro; }
}

function mudarPagina(diferenca) {
  if (!pdf) return;
  pagina = Math.min(pdf.numPages, Math.max(1, pagina + diferenca));
  renderizar();
}
anterior.addEventListener("click", () => mudarPagina(-1));
proxima.addEventListener("click", () => mudarPagina(1));
addEventListener("keydown", evento => {
  if (evento.key === "ArrowLeft") mudarPagina(-1);
  if (evento.key === "ArrowRight") mudarPagina(1);
});
let redimensionar;
addEventListener("resize", () => {
  clearTimeout(redimensionar);
  redimensionar = setTimeout(() => { if (pdf) renderizar(); }, 150);
});

try {
  const arquivo = new URLSearchParams(location.search).get("arquivo") || "";
  if (!/^(?:apresentacoes|geradas)\/[A-Za-z0-9_-]+\.pdf$/.test(arquivo)) throw Error("Arquivo inválido");
  const url = new URL(arquivo, location.href);
  document.querySelector("#direto").href = url.href;
  document.querySelector("#baixar").href = url.href;
  document.querySelector("#baixar").download = arquivo.split("/").pop();
  pdf = await getDocument({ url: url.href, isEvalSupported: false, enableXfa: false, useWasm: false }).promise;
  await renderizar();
} catch (erro) {
  status.hidden = false;
  status.textContent = "Não foi possível abrir a apresentação. Use PDF direto ou Baixar PDF.";
}
