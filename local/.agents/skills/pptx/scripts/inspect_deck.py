#!/usr/bin/env python3
import sys
import os
import json
import argparse

try:
    from pptx import Presentation
except ImportError:
    print(
        "❌ Error: 'python-pptx' no está instalado.\n"
        "Ejecutá:\n"
        "  python3 -m venv local/.agents/skills/pptx/.venv\n"
        "  local/.agents/skills/pptx/.venv/bin/pip install python-pptx\n"
        "  local/.agents/skills/pptx/.venv/bin/python local/.agents/skills/pptx/scripts/inspect_deck.py ...",
        file=sys.stderr
    )
    sys.exit(1)


def inspect_presentation(pptx_path):
    if not os.path.exists(pptx_path):
        print(f"❌ Archivo no encontrado: {pptx_path}", file=sys.stderr)
        sys.exit(1)

    prs = Presentation(pptx_path)
    slides_info = []

    for idx, slide in enumerate(prs.slides, start=1):
        layout_name = slide.slide_layout.name if slide.slide_layout else "Unknown"
        slide_title = ""
        if slide.shapes.title and slide.shapes.title.text:
            slide_title = slide.shapes.title.text.strip()

        texts = []
        tables = []

        for shape_idx, shape in enumerate(slide.shapes):
            if shape.has_text_frame:
                for p in shape.text_frame.paragraphs:
                    text_content = p.text.strip()
                    if text_content and text_content not in texts:
                        texts.append(text_content)

            elif shape.has_table:
                table_data = []
                for row in shape.table.rows:
                    row_data = [cell.text.strip() for cell in row.cells]
                    table_data.append(row_data)
                tables.append(table_data)

        # Notas del presentador si existen
        notes_text = ""
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
            notes_text = slide.notes_slide.notes_text_frame.text.strip()

        slides_info.append({
            "slide_number": idx,
            "title": slide_title,
            "layout": layout_name,
            "shapes_count": len(slide.shapes),
            "texts": texts,
            "tables_count": len(tables),
            "tables": tables if tables else None,
            "notes": notes_text if notes_text else None
        })

    return {
        "file": pptx_path,
        "total_slides": len(prs.slides),
        "slide_width_inches": round(prs.slide_width.inches, 2),
        "slide_height_inches": round(prs.slide_height.inches, 2),
        "slides": slides_info
    }


def main():
    parser = argparse.ArgumentParser(description="Inspecciona el contenido y estructura de un archivo PPTX")
    parser.add_argument("--input", "-i", required=True, help="Ruta al archivo .pptx")
    parser.add_argument("--json", action="store_true", help="Salida en formato JSON compacto")

    args = parser.parse_args()
    info = inspect_presentation(args.input)

    if args.json:
        print(json.dumps(info, indent=2, ensure_ascii=False))
    else:
        print(f"\n📊 Archivo: {info['file']}")
        print(f"Dimensiones: {info['slide_width_inches']}\" x {info['slide_height_inches']}\" | Total Slides: {info['total_slides']}\n")
        print("=" * 60)
        for s in info["slides"]:
            print(f"Slide #{s['slide_number']} | Título: '{s['title'] or '(Sin título)'}' | Layout: {s['layout']}")
            if s["texts"]:
                print("  Textos encontrados:")
                for t in s["texts"]:
                    preview = (t[:75] + "...") if len(t) > 75 else t
                    print(f"    - {preview}")
            if s["tables"]:
                print(f"  Tablas: {s['tables_count']} tabla(s)")
            if s["notes"]:
                print(f"  Notas: {s['notes'][:60]}...")
            print("-" * 60)


if __name__ == "__main__":
    main()
