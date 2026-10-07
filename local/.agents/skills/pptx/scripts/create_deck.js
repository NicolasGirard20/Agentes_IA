#!/usr/bin/env node
import pptxgen from "pptxgenjs";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Temas visuales modernos con paletas armónicas y contraste accesible
const THEMES = {
  "minimal-light": {
    bg: "F8FAFC",
    surface: "FFFFFF",
    surfaceBorder: "E2E8F0",
    textPrimary: "0F172A",
    textSecondary: "475569",
    accent: "2563EB",
    accentLight: "DBEAFE",
    badgeText: "1E40AF"
  },
  "dark-modern": {
    bg: "0F172A",
    surface: "1E293B",
    surfaceBorder: "334155",
    textPrimary: "F8FAFC",
    textSecondary: "94A3B8",
    accent: "38BDF8",
    accentLight: "0369A1",
    badgeText: "E0F2FE"
  },
  "emerald-corporate": {
    bg: "F0FDF4",
    surface: "FFFFFF",
    surfaceBorder: "DCFCE7",
    textPrimary: "064E3B",
    textSecondary: "166534",
    accent: "059669",
    accentLight: "D1FAE5",
    badgeText: "065F46"
  },
  "indigo-future": {
    bg: "F5F3FF",
    surface: "FFFFFF",
    surfaceBorder: "DDD6FE",
    textPrimary: "2E1065",
    textSecondary: "5B21B6",
    accent: "6366F1",
    accentLight: "EDE9FE",
    badgeText: "4338CA"
  }
};

function parseArgs() {
  const args = process.argv.slice(2);
  const options = {
    config: null,
    output: "presentation.pptx",
    demo: false
  };

  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--config" && args[i + 1]) {
      options.config = args[++i];
    } else if (args[i] === "--output" && args[i + 1]) {
      options.output = args[++i];
    } else if (args[i] === "--demo") {
      options.demo = true;
    }
  }

  return options;
}

function getSampleDeck() {
  return {
    title: "Estrategia de Agentes de IA",
    theme: "dark-modern",
    slides: [
      {
        type: "title",
        title: "Estrategia de Agentes Autónomos",
        subtitle: "Arquitectura Multi-Agente y Flujo de Trabajo en OpenCode",
        footer: "Q4 Roadmap • Tech Team"
      },
      {
        type: "cards",
        title: "Pilares del Ecosistema",
        subtitle: "Especialización de responsabilidades para máxima trazabilidad",
        cards: [
          {
            badge: "PRODUCTO",
            title: "Product Owner",
            desc: "Convierte requerimientos en criterios observables y formula opciones cerradas para el usuario."
          },
          {
            badge: "ANÁLISIS",
            title: "Planificador",
            desc: "Mapea dependencias, evalúa trade-offs y produce el plan de ejecución validado."
          },
          {
            badge: "CALIDAD",
            title: "Tester",
            desc: "Valida la implementación con pruebas específicas antes de liberar cambios."
          }
        ]
      },
      {
        type: "split",
        title: "Flujo de Ejecución Orquestado",
        subtitle: "Coordinación secuencial y aprobaciones explícitas",
        left: {
          header: "Beneficios de la Arquitectura",
          points: [
            "El usuario no tiene que tipear explicaciones largas gracias a preguntas con opciones.",
            "Cada agente tiene permisos estrictos según su rol (read, edit, bash).",
            "Métricas de consumo de tokens registradas en cada paso."
          ]
        },
        right: {
          badge: "MÉTRICA CLAVE",
          title: "85% Reducción de Ruido",
          desc: "Al utilizar opciones cerradas [A], [B], [C], el feedback se procesa en un solo ciclo sin desvíos."
        }
      },
      {
        type: "quote",
        title: "Conclusión",
        quote: "La especialización de agentes combinada con decisiones en formato de opciones elimina la ambigüedad y acelera la construcción de software.",
        author: "Arquitectura de Agentes IA"
      }
    ]
  };
}

export async function generatePresentation(deckData, outputPath) {
  const prs = new pptxgen();
  prs.layout = "LAYOUT_16x9"; // 13.33 x 7.5 pulgadas

  const themeKey = deckData.theme || "minimal-light";
  const theme = THEMES[themeKey] || THEMES["minimal-light"];

  for (const slideData of deckData.slides || []) {
    const slide = prs.addSlide();
    slide.background = { color: theme.bg };

    switch (slideData.type) {
      case "title":
        renderTitleSlide(slide, slideData, theme);
        break;
      case "cards":
        renderCardsSlide(slide, slideData, theme);
        break;
      case "split":
        renderSplitSlide(slide, slideData, theme);
        break;
      case "bullets":
        renderBulletsSlide(slide, slideData, theme);
        break;
      case "quote":
        renderQuoteSlide(slide, slideData, theme);
        break;
      case "table":
        renderTableSlide(slide, slideData, theme);
        break;
      default:
        renderGenericSlide(slide, slideData, theme);
    }
  }

  await prs.writeFile({ fileName: outputPath });
  console.log(`✅ Presentación generada exitosamente en: ${outputPath}`);
}

function renderTitleSlide(slide, data, theme) {
  // Card central decorativa
  slide.addShape("roundRect", {
    x: 1.0,
    y: 1.2,
    w: 11.33,
    h: 5.1,
    fill: { color: theme.surface },
    line: { color: theme.surfaceBorder, width: 1 },
    rectRadius: 0.15
  });

  // Tira de acento
  slide.addShape("rect", {
    x: 1.0,
    y: 1.2,
    w: 0.25,
    h: 5.1,
    fill: { color: theme.accent }
  });

  // Título
  slide.addText(data.title, {
    x: 1.6,
    y: 2.2,
    w: 10.0,
    h: 1.6,
    fontSize: 34,
    bold: true,
    color: theme.textPrimary,
    fontFace: "Arial",
    valign: "top"
  });

  // Subtítulo
  if (data.subtitle) {
    slide.addText(data.subtitle, {
      x: 1.6,
      y: 4.0,
      w: 10.0,
      h: 1.0,
      fontSize: 18,
      color: theme.textSecondary,
      fontFace: "Arial",
      valign: "top"
    });
  }

  // Footer / Metadatos
  if (data.footer) {
    slide.addText(data.footer, {
      x: 1.6,
      y: 5.4,
      w: 10.0,
      h: 0.5,
      fontSize: 12,
      color: theme.accent,
      bold: true,
      fontFace: "Arial"
    });
  }
}

function renderCardsSlide(slide, data, theme) {
  // Encabezado de slide
  renderSlideHeader(slide, data, theme);

  const cards = data.cards || [];
  const count = Math.min(cards.length, 4);
  if (count === 0) return;

  const totalWidth = 11.73;
  const gap = 0.35;
  const cardWidth = (totalWidth - gap * (count - 1)) / count;
  const startX = 0.8;
  const startY = 2.1;
  const cardHeight = 4.6;

  cards.slice(0, count).forEach((card, idx) => {
    const x = startX + idx * (cardWidth + gap);

    // Contenedor Card
    slide.addShape("roundRect", {
      x,
      y: startY,
      w: cardWidth,
      h: cardHeight,
      fill: { color: theme.surface },
      line: { color: theme.surfaceBorder, width: 1 },
      rectRadius: 0.12
    });

    let currentY = startY + 0.3;

    // Badge
    if (card.badge) {
      slide.addShape("roundRect", {
        x: x + 0.25,
        y: currentY,
        w: 1.6,
        h: 0.35,
        fill: { color: theme.accentLight },
        rectRadius: 0.08
      });
      slide.addText(card.badge, {
        x: x + 0.25,
        y: currentY,
        w: 1.6,
        h: 0.35,
        fontSize: 9,
        bold: true,
        color: theme.badgeText,
        align: "center",
        valign: "middle"
      });
      currentY += 0.55;
    }

    // Título de la tarjeta
    slide.addText(card.title, {
      x: x + 0.25,
      y: currentY,
      w: cardWidth - 0.5,
      h: 0.8,
      fontSize: 18,
      bold: true,
      color: theme.textPrimary,
      fontFace: "Arial"
    });
    currentY += 0.9;

    // Descripción
    slide.addText(card.desc, {
      x: x + 0.25,
      y: currentY,
      w: cardWidth - 0.5,
      h: 2.4,
      fontSize: 13,
      color: theme.textSecondary,
      fontFace: "Arial",
      valign: "top"
    });
  });
}

function renderSplitSlide(slide, data, theme) {
  renderSlideHeader(slide, data, theme);

  const startY = 2.1;
  const halfWidth = 5.65;

  // Lado izquierdo: Puntos clave
  slide.addShape("roundRect", {
    x: 0.8,
    y: startY,
    w: halfWidth,
    h: 4.6,
    fill: { color: theme.surface },
    line: { color: theme.surfaceBorder, width: 1 },
    rectRadius: 0.12
  });

  if (data.left?.header) {
    slide.addText(data.left.header, {
      x: 1.1,
      y: startY + 0.3,
      w: halfWidth - 0.6,
      h: 0.6,
      fontSize: 18,
      bold: true,
      color: theme.textPrimary,
      fontFace: "Arial"
    });
  }

  if (data.left?.points) {
    const bullets = data.left.points.map((pt) => ({
      text: pt,
      options: { fontSize: 13, color: theme.textSecondary, bullet: true, breakLine: true }
    }));
    slide.addText(bullets, {
      x: 1.1,
      y: startY + 1.0,
      w: halfWidth - 0.6,
      h: 3.2,
      fontFace: "Arial",
      valign: "top"
    });
  }

  // Lado derecho: Tarjeta de destaque / Métrica
  const rightX = 0.8 + halfWidth + 0.43;
  slide.addShape("roundRect", {
    x: rightX,
    y: startY,
    w: halfWidth,
    h: 4.6,
    fill: { color: theme.surface },
    line: { color: theme.accent, width: 2 },
    rectRadius: 0.12
  });

  if (data.right?.badge) {
    slide.addShape("roundRect", {
      x: rightX + 0.4,
      y: startY + 0.4,
      w: 1.8,
      h: 0.35,
      fill: { color: theme.accentLight },
      rectRadius: 0.08
    });
    slide.addText(data.right.badge, {
      x: rightX + 0.4,
      y: startY + 0.4,
      w: 1.8,
      h: 0.35,
      fontSize: 9,
      bold: true,
      color: theme.badgeText,
      align: "center",
      valign: "middle"
    });
  }

  if (data.right?.title) {
    slide.addText(data.right.title, {
      x: rightX + 0.4,
      y: startY + 1.0,
      w: halfWidth - 0.8,
      h: 1.0,
      fontSize: 26,
      bold: true,
      color: theme.accent,
      fontFace: "Arial"
    });
  }

  if (data.right?.desc) {
    slide.addText(data.right.desc, {
      x: rightX + 0.4,
      y: startY + 2.2,
      w: halfWidth - 0.8,
      h: 2.0,
      fontSize: 14,
      color: theme.textSecondary,
      fontFace: "Arial",
      valign: "top"
    });
  }
}

function renderBulletsSlide(slide, data, theme) {
  renderSlideHeader(slide, data, theme);

  slide.addShape("roundRect", {
    x: 0.8,
    y: 2.1,
    w: 11.73,
    h: 4.6,
    fill: { color: theme.surface },
    line: { color: theme.surfaceBorder, width: 1 },
    rectRadius: 0.12
  });

  const bullets = (data.points || []).map((p) => ({
    text: p,
    options: {
      fontSize: 15,
      color: theme.textPrimary,
      bullet: true,
      breakLine: true
    }
  }));

  slide.addText(bullets, {
    x: 1.3,
    y: 2.6,
    w: 10.73,
    h: 3.6,
    fontFace: "Arial",
    valign: "top"
  });
}

function renderQuoteSlide(slide, data, theme) {
  renderSlideHeader(slide, data, theme);

  slide.addShape("roundRect", {
    x: 1.5,
    y: 2.2,
    w: 10.33,
    h: 4.4,
    fill: { color: theme.surface },
    line: { color: theme.accent, width: 1.5 },
    rectRadius: 0.15
  });

  slide.addText(`“${data.quote}”`, {
    x: 2.0,
    y: 2.8,
    w: 9.33,
    h: 2.2,
    fontSize: 22,
    italic: true,
    color: theme.textPrimary,
    fontFace: "Arial",
    align: "center",
    valign: "middle"
  });

  if (data.author) {
    slide.addText(`— ${data.author}`, {
      x: 2.0,
      y: 5.2,
      w: 9.33,
      h: 0.6,
      fontSize: 14,
      bold: true,
      color: theme.accent,
      fontFace: "Arial",
      align: "center"
    });
  }
}

function renderTableSlide(slide, data, theme) {
  renderSlideHeader(slide, data, theme);

  const rows = [];
  if (data.headers) {
    rows.push(
      data.headers.map((h) => ({
        text: h,
        options: {
          bold: true,
          fill: theme.accent,
          color: "FFFFFF",
          fontSize: 13,
          align: "center"
        }
      }))
    );
  }

  (data.rows || []).forEach((row, rIdx) => {
    const isAlt = rIdx % 2 === 1;
    rows.push(
      row.map((cell) => ({
        text: cell,
        options: {
          fill: isAlt ? theme.surfaceBorder : theme.surface,
          color: theme.textPrimary,
          fontSize: 12
        }
      }))
    );
  });

  slide.addTable(rows, {
    x: 0.8,
    y: 2.1,
    w: 11.73,
    colW: data.colWidths,
    border: { color: theme.surfaceBorder, pt: 1 }
  });
}

function renderSlideHeader(slide, data, theme) {
  slide.addText(data.title || "Sin Título", {
    x: 0.8,
    y: 0.6,
    w: 11.73,
    h: 0.8,
    fontSize: 26,
    bold: true,
    color: theme.textPrimary,
    fontFace: "Arial"
  });

  if (data.subtitle) {
    slide.addText(data.subtitle, {
      x: 0.8,
      y: 1.35,
      w: 11.73,
      h: 0.5,
      fontSize: 14,
      color: theme.textSecondary,
      fontFace: "Arial"
    });
  }
}

function renderGenericSlide(slide, data, theme) {
  renderSlideHeader(slide, data, theme);
  slide.addText(data.content || "", {
    x: 0.8,
    y: 2.2,
    w: 11.73,
    h: 4.5,
    fontSize: 14,
    color: theme.textPrimary
  });
}

async function main() {
  const options = parseArgs();

  let deckData;
  if (options.config) {
    const configPath = path.resolve(options.config);
    if (!fs.existsSync(configPath)) {
      console.error(`❌ Archivo de configuración no encontrado: ${configPath}`);
      process.exit(1);
    }
    deckData = JSON.parse(fs.readFileSync(configPath, "utf-8"));
  } else if (options.demo || !options.config) {
    console.log("ℹ️  Generando presentación demo (usa --config <path.json> para datos propios)");
    deckData = getSampleDeck();
  }

  await generatePresentation(deckData, options.output);
}

// Ejecutar si es CLI
if (process.argv[1] && process.argv[1].endsWith("create_deck.js")) {
  main().catch((err) => {
    console.error("❌ Error generando presentación:", err);
    process.exit(1);
  });
}
