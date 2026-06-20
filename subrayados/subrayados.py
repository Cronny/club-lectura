#!/usr/bin/env python3
"""
Convierte metadata.epub.lua (KOReader) en una nota de Obsidian con los subrayados.

Uso:
    python subrayados.py <metadata.epub.lua> [salida.md]

Si se omite la ruta de salida, el archivo se guarda en el mismo directorio
que el .lua con un nombre derivado del título del libro.

Requiere:
    pip install lupa
"""

import sys
import re
from datetime import datetime
from pathlib import Path
from collections import defaultdict


def _importar_lupa():
    try:
        from lupa import LuaRuntime
        return LuaRuntime
    except ImportError:
        sys.exit(
            "Error: lupa no está instalado.\n"
            "Instálalo con:  pip install lupa"
        )


def cargar_tabla(ruta: str):
    LuaRuntime = _importar_lupa()
    lua = LuaRuntime(unpack_returned_tuples=True)
    contenido = Path(ruta).read_text(encoding="utf-8")
    # eval() solo acepta expresiones; el archivo usa `return {...}` (chunk).
    # Lo ejecutamos como cuerpo de una función anónima y guardamos en un global.
    lua.execute(f"_data = (function()\n{contenido}\nend)()")
    tabla = lua.globals()._data
    return lua, tabla


def extraer_subrayados(lua, tabla) -> list[dict]:
    subrayados = []
    annotations = tabla["annotations"]
    # Usamos el operador # de Lua para el conteo en lugar de ipairs,
    # ya que unpack_returned_tuples cambia el comportamiento del iterador.
    n = lua.eval("#_data.annotations")

    for i in range(1, n + 1):
        entry = annotations[i]
        text = entry["text"]
        if not text or not text.strip():
            continue

        dt_str = entry["datetime"]
        try:
            dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            dt = datetime.min

        note = entry["note"]

        subrayados.append({
            "text": text,
            "pageno": int(entry["pageno"]),
            "datetime": dt,
            "chapter": entry["chapter"] or "Sin capítulo",
            "note": note if note else None,
        })

    return subrayados


def agrupar_por_capitulo(subrayados: list[dict]) -> tuple[list[str], dict]:
    """
    Devuelve (orden_capitulos, grupos) donde:
    - orden_capitulos: capítulos en el orden de su primera aparición cronológica
    - grupos[cap]: subrayados de ese capítulo, ordenados por datetime
    """
    subrayados_sorted = sorted(subrayados, key=lambda x: x["datetime"])

    orden = []
    grupos: dict[str, list] = defaultdict(list)

    for s in subrayados_sorted:
        ch = s["chapter"]
        if ch not in grupos:
            orden.append(ch)
        grupos[ch].append(s)

    return orden, grupos


def nombre_archivo(titulo: str) -> str:
    seguro = re.sub(r'[\\/:*?"<>|]', "", titulo)
    seguro = seguro.strip(". ").rstrip()
    if len(seguro) > 80:
        seguro = seguro[:80].rstrip()
    return f"{seguro} — Subrayados.md"


def render_markdown(tabla, subrayados: list[dict]) -> str:
    doc_props = tabla["doc_props"]
    titulo = doc_props["title"] or "Sin título"
    autor = doc_props["authors"] or "Autor desconocido"
    total = len(subrayados)
    hoy = datetime.now().strftime("%Y-%m-%d")

    orden, grupos = agrupar_por_capitulo(subrayados)

    L = []

    # Frontmatter YAML
    L += [
        "---",
        f'title: "Subrayados — {titulo}"',
        f'author: "{autor}"',
        "tags:",
        "  - subrayados",
        "  - lectura",
        f"total_subrayados: {total}",
        f"fecha_generacion: {hoy}",
        "---",
        "",
    ]

    # Cabecera del documento
    L += [
        f"# {titulo}",
        f"**{autor}**",
        "",
        f"*{total} subrayados*",
        "",
        "---",
        "",
    ]

    # Subrayados agrupados por capítulo
    for capitulo in orden:
        entradas = grupos[capitulo]
        L += [f"## {capitulo}", ""]

        for s in entradas:
            dt_fmt = s["datetime"].strftime("%Y-%m-%d %H:%M")
            L.append(f'> {s["text"]}')
            L.append("")
            meta = f'📄 p. {s["pageno"]} · 🗓️ {dt_fmt}'
            if s["note"]:
                meta += f' · 💬 {s["note"]}'
            L.append(meta)
            L.append("")

        L += ["---", ""]

    return "\n".join(L)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    ruta_lua = Path(sys.argv[1])
    if not ruta_lua.exists():
        sys.exit(f"Error: no se encuentra el archivo '{ruta_lua}'")

    print(f"Cargando {ruta_lua}...")
    lua, tabla = cargar_tabla(str(ruta_lua))

    print("Extrayendo subrayados...")
    subrayados = extraer_subrayados(lua, tabla)
    print(f"  {len(subrayados)} subrayados encontrados")

    # Determinar ruta de salida
    if len(sys.argv) >= 3:
        ruta_md = Path(sys.argv[2])
    else:
        doc_props = tabla["doc_props"]
        titulo = doc_props["title"] or "subrayados"
        ruta_md = ruta_lua.parent / nombre_archivo(titulo)

    print("Generando nota Obsidian...")
    md = render_markdown(tabla, subrayados)

    ruta_md.write_text(md, encoding="utf-8")
    print(f"Nota guardada en: {ruta_md}")


if __name__ == "__main__":
    main()
