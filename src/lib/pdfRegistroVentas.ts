export interface ProductoMasVendidoInfo {
  nombre: string;
  cantidad: number;
}

export interface ItemDesglosePDF {
  nombre: string;
  cantidad: number;
  subtotal: number;
}

export interface RegistroDiaVenta {
  fecha_operativa: string;
  fecha_operativa_etiqueta: string;
  reinicios_realizados: number;
  cuentas_totales: number;
  subtotal_ventas: number;
  propinas_totales: number;
  total_general: number;
  total_efectivo: number;
  total_tarjeta: number;
  producto_mas_vendido: ProductoMasVendidoInfo | null;
  alimento_mas_vendido: ProductoMasVendidoInfo | null;
  bebida_mas_vendido: ProductoMasVendidoInfo | null;
  combo_mas_vendido: ProductoMasVendidoInfo | null;
  desglose_alimentos: ItemDesglosePDF[];
  subtotal_alimentos: number;
  desglose_bebidas: ItemDesglosePDF[];
  subtotal_bebidas: number;
  desglose_combos: ItemDesglosePDF[];
  subtotal_combos: number;
}

function sanitizarPdfTexto(texto: string): string {
  const sinAcentos = texto
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^\x20-\x7E]/g, " ");
  return sinAcentos.replace(/\\/g, "\\\\").replace(/\(/g, "\\(").replace(/\)/g, "\\)");
}

function fmtMoney(n: number): string {
  return `$${Number(n || 0).toFixed(2)}`;
}

function construirPaginasDeUnDia(reg: RegistroDiaVenta): string[][] {
  const pages: string[][] = [];

  // Página 1: Resumen general del día
  const p1: string[] = [
    "BT",
    "/F2 16 Tf",
    "50 740 Td",
    "(RESUMEN DEL DIA - REGISTRO DE VENTAS) Tj",
    "/F1 11 Tf",
    "0 -22 Td",
    `(${sanitizarPdfTexto(`Dia: ${reg.fecha_operativa_etiqueta}`)}) Tj`,
    "0 -16 Td",
    `(${sanitizarPdfTexto(`Reinicios de dia realizados: ${reg.reinicios_realizados}`)}) Tj`,
    "0 -24 Td",
    `(${sanitizarPdfTexto(`Total vendido (subtotal productos): ${fmtMoney(reg.subtotal_ventas)}`)}) Tj`,
    "0 -18 Td",
    `(${sanitizarPdfTexto(`Total general cobrado: ${fmtMoney(reg.total_general)}`)}) Tj`,
    "0 -18 Td",
    `(${sanitizarPdfTexto(`Propinas totales: ${fmtMoney(reg.propinas_totales)}`)}) Tj`,
    "0 -18 Td",
    `(${sanitizarPdfTexto(`Cuentas totales del dia: ${reg.cuentas_totales}`)}) Tj`,
    "0 -26 Td",
    "/F2 12 Tf",
    "(MAS VENDIDOS DEL DIA) Tj",
    "/F1 11 Tf",
    "0 -18 Td",
    `(${sanitizarPdfTexto(
      `Producto mas vendido: ${
        reg.producto_mas_vendido
          ? `${reg.producto_mas_vendido.nombre} (${reg.producto_mas_vendido.cantidad})`
          : "Sin ventas"
      }`
    )}) Tj`,
    "0 -18 Td",
    `(${sanitizarPdfTexto(
      `Alimento mas vendido: ${
        reg.alimento_mas_vendido
          ? `${reg.alimento_mas_vendido.nombre} (${reg.alimento_mas_vendido.cantidad})`
          : "Sin alimentos"
      }`
    )}) Tj`,
    "0 -18 Td",
    `(${sanitizarPdfTexto(
      `Bebida mas vendida: ${
        reg.bebida_mas_vendido
          ? `${reg.bebida_mas_vendido.nombre} (${reg.bebida_mas_vendido.cantidad})`
          : "Sin bebidas"
      }`
    )}) Tj`,
    "0 -18 Td",
    `(${sanitizarPdfTexto(
      `Combo mas vendido: ${
        reg.combo_mas_vendido
          ? `${reg.combo_mas_vendido.nombre} (${reg.combo_mas_vendido.cantidad})`
          : "Sin combos"
      }`
    )}) Tj`,
    "ET",
  ];
  pages.push(p1);

  const agregarSeccionPaginada = (
    tituloSeccion: string,
    etiquetaSubtotal: string,
    items: ItemDesglosePDF[],
    subtotal: number
  ) => {
    const porPagina = 28;
    const chunks: ItemDesglosePDF[][] = [];
    if (items.length === 0) {
      chunks.push([]);
    } else {
      for (let i = 0; i < items.length; i += porPagina) {
        chunks.push(items.slice(i, i + porPagina));
      }
    }

    chunks.forEach((bloque, idx) => {
      const ops: string[] = [
        "BT",
        "/F2 15 Tf",
        "50 740 Td",
        `(${sanitizarPdfTexto(
          `${tituloSeccion}${chunks.length > 1 ? ` (Pag. ${idx + 1}/${chunks.length})` : ""}`
        )}) Tj`,
        "/F1 10 Tf",
        "0 -16 Td",
        `(${sanitizarPdfTexto(reg.fecha_operativa_etiqueta)}) Tj`,
        "0 -22 Td",
      ];

      if (bloque.length === 0) {
        ops.push("(Sin registros en esta categoria.) Tj");
      } else {
        for (const it of bloque) {
          ops.push(
            `(${sanitizarPdfTexto(
              `${it.cantidad}x  ${it.nombre}  -  ${fmtMoney(it.subtotal)}`
            )}) Tj`,
            "0 -16 Td"
          );
        }
      }

      if (idx === chunks.length - 1) {
        ops.push(
          "0 -16 Td",
          "/F2 12 Tf",
          `(${sanitizarPdfTexto(`${etiquetaSubtotal}: ${fmtMoney(subtotal)}`)}) Tj`
        );
      }

      ops.push("ET");
      pages.push(ops);
    });
  };

  agregarSeccionPaginada(
    "DESGLOSE DE ALIMENTOS",
    "SUBTOTAL VENDIDO SOLO DE ALIMENTOS",
    reg.desglose_alimentos || [],
    reg.subtotal_alimentos || 0
  );

  agregarSeccionPaginada(
    "DESGLOSE DE BEBIDAS",
    "SUBTOTAL VENDIDO SOLO DE BEBIDAS",
    reg.desglose_bebidas || [],
    reg.subtotal_bebidas || 0
  );

  agregarSeccionPaginada(
    "DESGLOSE DE COMBOS",
    "SUBTOTAL VENDIDO SOLO DE COMBOS",
    reg.desglose_combos || [],
    reg.subtotal_combos || 0
  );

  return pages;
}

function ensamblarPdfDesdePaginas(allPageStreams: string[][]): Blob {
  const objects: string[] = [];
  const pageObjNumbers: number[] = [];

  const catalogId = 1;
  const pagesId = 2;
  const fontRegularId = 3;
  const fontBoldId = 4;

  let nextId = 5;
  const pageDefs: { pageId: number; contentId: number; stream: string }[] = [];

  for (const ops of allPageStreams) {
    const contentStream = ops.join("\n");
    const pageId = nextId++;
    const contentId = nextId++;
    pageObjNumbers.push(pageId);
    pageDefs.push({ pageId, contentId, stream: contentStream });
  }

  objects.push(`${catalogId} 0 obj\n<< /Type /Catalog /Pages ${pagesId} 0 R >>\nendobj\n`);
  objects.push(
    `${pagesId} 0 obj\n<< /Type /Pages /Kids [${pageObjNumbers
      .map((id) => `${id} 0 R`)
      .join(" ")}] /Count ${pageObjNumbers.length} >>\nendobj\n`
  );
  objects.push(
    `${fontRegularId} 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n`
  );
  objects.push(
    `${fontBoldId} 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>\nendobj\n`
  );

  for (const pd of pageDefs) {
    objects.push(
      `${pd.pageId} 0 obj\n<< /Type /Page /Parent ${pagesId} 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 ${fontRegularId} 0 R /F2 ${fontBoldId} 0 R >> >> /Contents ${pd.contentId} 0 R >>\nendobj\n`
    );
    objects.push(
      `${pd.contentId} 0 obj\n<< /Length ${pd.stream.length} >>\nstream\n${pd.stream}\nendstream\nendobj\n`
    );
  }

  let pdf = "%PDF-1.4\n";
  const offsets: number[] = [0];

  for (const obj of objects) {
    offsets.push(pdf.length);
    pdf += obj;
  }

  const xrefStart = pdf.length;
  pdf += `xref\n0 ${objects.length + 1}\n`;
  pdf += "0000000000 65535 f \n";
  for (let i = 1; i < offsets.length; i++) {
    pdf += `${String(offsets[i]).padStart(10, "0")} 00000 n \n`;
  }

  pdf += `trailer\n<< /Size ${objects.length + 1} /Root ${catalogId} 0 R >>\nstartxref\n${xrefStart}\n%%EOF`;

  return new Blob([pdf], { type: "application/pdf" });
}

function dispararDescargaBlob(blob: Blob, nombreArchivo: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = nombreArchivo;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1500);
}

export function descargarPdfRegistroDia(reg: RegistroDiaVenta) {
  const pages = construirPaginasDeUnDia(reg);
  const blob = ensamblarPdfDesdePaginas(pages);
  dispararDescargaBlob(blob, `registro-ventas-${reg.fecha_operativa}.pdf`);
}

export function descargarPdfTodosLosRegistros(
  registros: RegistroDiaVenta[],
  mesNombre: string,
  anio: number
) {
  const todasLasPaginas: string[][] = [];
  for (const reg of registros) {
    todasLasPaginas.push(...construirPaginasDeUnDia(reg));
  }
  if (todasLasPaginas.length === 0) {
    todasLasPaginas.push([
      "BT",
      "/F2 15 Tf",
      "50 740 Td",
      `(${sanitizarPdfTexto(`REGISTRO DE VENTAS - ${mesNombre.toUpperCase()} ${anio}`)}) Tj`,
      "/F1 11 Tf",
      "0 -24 Td",
      "(No hay registros de dias guardados hasta el momento.) Tj",
      "ET",
    ]);
  }
  const blob = ensamblarPdfDesdePaginas(todasLasPaginas);
  dispararDescargaBlob(blob, `registro-ventas-${mesNombre.toLowerCase()}-${anio}.pdf`);
}
