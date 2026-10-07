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
        "  local/.agents/skills/pptx/.venv/bin/python local/.agents/skills/pptx/scripts/modify_deck.py ...",
        file=sys.stderr
    )
    sys.exit(1)


def replace_text_in_paragraph(paragraph, replacements):
    """
    Reemplaza texto preservando formato a nivel de run cuando es posible,
    o en el párrafo completo si la frase abarca múltiples runs.
    """
    modified = False
    full_text = paragraph.text

    # Primero intentamos reemplazar a nivel de run individual (preserva formato perfecto)
    for run in paragraph.runs:
        for old_str, new_str in replacements.items():
            if old_str in run.text:
                run.text = run.text.replace(old_str, new_str)
                modified = True

    # Si la cadena no estaba en un solo run pero sí en el párrafo concatenado
    if not modified:
        for old_str, new_str in replacements.items():
            if old_str in full_text:
                new_text = full_text.replace(old_str, new_str)
                paragraph.text = new_text
                modified = True
                break

    return modified


def modify_presentation(input_path, output_path, replacements=None, slide_edits=None):
    if not os.path.exists(input_path):
        print(f"❌ Archivo no encontrado: {input_path}", file=sys.stderr)
        sys.exit(1)

    prs = Presentation(input_path)
    replacements = replacements or {}
    total_replacements = 0

    # 1. Aplicar reemplazos globales de texto
    if replacements:
        for slide in prs.slides:
            for shape in slide.shapes:
                if shape.has_text_frame:
                    for paragraph in shape.text_frame.paragraphs:
                        if replace_text_in_paragraph(paragraph, replacements):
                            total_replacements += 1

                elif shape.has_table:
                    for row in shape.table.rows:
                        for cell in row.cells:
                            for paragraph in cell.text_frame.paragraphs:
                                if replace_text_in_paragraph(paragraph, replacements):
                                    total_replacements += 1

    # 2. Aplicar modificaciones por slide puntual (si se especifica slide_edits)
    # Formato de slide_edits: [{"slide": 1, "title": "Nuevo", "add_bullet": "Nuevo punto", "notes": "..."}]
    if slide_edits:
        for edit in slide_edits:
            slide_idx = edit.get("slide", 1) - 1
            if 0 <= slide_idx < len(prs.slides):
                slide = prs.slides[slide_idx]

                if "title" in edit and slide.shapes.title:
                    slide.shapes.title.text = edit["title"]

                if "notes" in edit:
                    notes_slide = slide.notes_slide
                    notes_slide.notes_text_frame.text = edit["notes"]

    prs.save(output_path)
    print(f"✅ Archivo modificado guardado exitosamente en: {output_path}")
    if replacements:
        print(f"ℹ️  Total de bloques de texto actualizados: {total_replacements}")


def main():
    parser = argparse.ArgumentParser(description="Modifica presentaciones PPTX existentes preservando estilos")
    parser.add_argument("--input", "-i", required=True, help="Ruta al archivo PPTX de origen")
    parser.add_argument("--output", "-o", required=True, help="Ruta de salida para el nuevo PPTX")
    parser.add_argument("--replace-json", help='JSON en línea con mapeo: \'{"texto viejo": "texto nuevo"}\'')
    parser.add_argument("--replace-file", help="Ruta a un archivo JSON con mapeo de reemplazos")
    parser.add_argument("--edits-file", help="Ruta a un archivo JSON con ediciones específicas por slide")

    args = parser.parse_args()

    replacements = {}
    if args.replace_json:
        try:
            replacements.update(json.loads(args.replace_json))
        except json.JSONDecodeError as e:
            print(f"❌ JSON inválido en --replace-json: {e}", file=sys.stderr)
            sys.exit(1)

    if args.replace_file:
        if not os.path.exists(args.replace_file):
            print(f"❌ Archivo no encontrado: {args.replace_file}", file=sys.stderr)
            sys.exit(1)
        with open(args.replace_file, "r", encoding="utf-8") as f:
            replacements.update(json.load(f))

    slide_edits = None
    if args.edits_file:
        if not os.path.exists(args.edits_file):
            print(f"❌ Archivo no encontrado: {args.edits_file}", file=sys.stderr)
            sys.exit(1)
        with open(args.edits_file, "r", encoding="utf-8") as f:
            slide_edits = json.load(f)

    if not replacements and not slide_edits:
        print("⚠️ Advertencia: No se especificaron reemplazos ni ediciones. Se guardará una copia exacta.")

    modify_presentation(args.input, args.output, replacements, slide_edits)


if __name__ == "__main__":
    main()
