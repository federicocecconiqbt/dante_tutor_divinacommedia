#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Divina Commedia (ed. Petrocchi) → JSON pipeline
------------------------------------------------
Given a PDF (Petrocchi), a cantica, a canto number, and a page range,
extract verses, group into terzine and recitation blocks, and emit a structured JSON.

USAGE (example):
    python divina_pipeline.py \
        --pdf "/path/to/Petrocchi_Commedia.pdf" \
        --cantica Inferno \
        --canto 5 \
        --start-page 123 --end-page 140 \
        --block-size 12 --block-overlap 0 \
        --output "/path/to/inf_05.json"

Notes:
- Requires PyPDF2 (pip install PyPDF2).
- Heuristics are intentionally simple; adjust filters for your specific PDF layout.
- We assume one verse per line in the extracted text (common in many scholarly PDFs).
"""

import re
import json
import argparse
from typing import List, Tuple, Dict, Any

try:
    import PyPDF2
except ImportError:
    PyPDF2 = None

# -----------------------------
# Helpers
# -----------------------------

CANTICA_MAP = {
    "inferno": "Inferno",
    "purgatorio": "Purgatorio",
    "paradiso": "Paradiso"
}

def short_cantica(cantica: str) -> str:
    c = cantica.strip().lower()
    if c.startswith("inf"):
        return "inf"
    if c.startswith("pur"):
        return "purg"
    if c.startswith("par"):
        return "par"
    raise ValueError(f"Cantica non riconosciuta: {cantica}")

def create_urn(cantica: str, canto: int, verse_number: int) -> str:
    return f"{short_cantica(cantica)}.{int(canto):02d}.{int(verse_number):03d}"

HEADER_PATTERNS = [
    r"^\s*CANTO\s+[IVXLCDM]+\s*$",
    r"^\s*(Inferno|Purgatorio|Paradiso)\s*$",
    r"^\s*DANTE\s+ALIGHIERI\s*$",
    r"^\s*LA\s+DIVINA\s+COMMEDIA\s*$",
]

FOOTER_PATTERNS = [
    r"^\s*\d+\s*$"  # page numbers alone
]

def is_header_footer(line: str) -> bool:
    for pat in HEADER_PATTERNS + FOOTER_PATTERNS:
        if re.match(pat, line, flags=re.IGNORECASE):
            return True
    return False

def clean_line(line: str) -> str:
    # Keep punctuation and accents; do a light trim
    line = line.replace("\u00ad", "")  # soft hyphen
    return line.strip()

def is_probable_verse(line: str) -> bool:
    if not line:
        return False
    if is_header_footer(line):
        return False
    # Filter out very short artifacts
    if len(line) < 2:
        return False
    # Avoid all-caps short headings (heuristic)
    if re.match(r"^[A-Z\s\.\-]+$", line) and len(line.split()) <= 4:
        return False
    return True

def extract_lines_from_pdf(pdf_path: str, start_page: int, end_page: int) -> List[str]:
    if PyPDF2 is None:
        raise RuntimeError("PyPDF2 non installato. Eseguire: pip install PyPDF2")
    lines: List[str] = []
    with open(pdf_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        n_pages = len(reader.pages)
        if start_page < 1 or end_page > n_pages or start_page > end_page:
            raise ValueError(f"Intervallo pagine non valido: 1..{n_pages}, richiesto {start_page}..{end_page}")
        for p in range(start_page - 1, end_page):
            page = reader.pages[p]
            text = page.extract_text() or ""
            # Normalize newlines and split
            for raw in text.splitlines():
                line = clean_line(raw)
                if is_probable_verse(line):
                    lines.append(line)
    return lines

def group_terzine(verses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    terzine = []
    for i in range(0, len(verses), 3):
        chunk = verses[i:i+3]
        if len(chunk) < 3:
            break
        start_urn = chunk[0]["urn"]
        end_urn = chunk[-1]["urn"]
        terzine.append({
            "urn": f"{start_urn.rsplit('.',1)[0]}.{int(chunk[0]['number']):03d}-{int(chunk[-1]['number']):03d}",
            "start_verso": chunk[0]["number"],
            "end_verso": chunk[-1]["number"],
            "rhyme_scheme": "aba",  # locale alla terzina (semplificazione)
            "versi": [v["urn"] for v in chunk]
        })
    return terzine

def make_ssml_for_verso(text: str) -> str:
    # Very light SSML; refine per your TTS engine
    # Mark primary stress visually could be complex; leave as plain.
    safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f"<s>{safe}</s>"

def make_ssml_for_block(verses_texts: List[str]) -> str:
    # Short pause after each verse, slightly longer after each 3 (terzina)
    parts = []
    for i, t in enumerate(verses_texts, start=1):
        parts.append(f"<s>{t}</s>")
        if i % 3 == 0:
            parts.append("<break time='220ms'/>")
        else:
            parts.append("<break time='120ms'/>")
    return f"<p>{''.join(parts)}</p>"

def build_recitation_blocks(verses: List[Dict[str, Any]], block_size: int, overlap: int) -> List[Dict[str, Any]]:
    blocks = []
    n = len(verses)
    if block_size <= 0:
        return blocks
    step = max(1, block_size - overlap)
    i = 0
    while i < n:
        chunk = verses[i:i+block_size]
        if not chunk:
            break
        start_no = chunk[0]["number"]
        end_no = chunk[-1]["number"]
        start_urn = chunk[0]["urn"]
        end_urn = chunk[-1]["urn"]
        ssml = make_ssml_for_block([c["text_original"] for c in chunk])
        blocks.append({
            "urn": f"{start_urn.rsplit('.',1)[0]}.{start_no:03d}-{end_no:03d}",
            "start_verso": start_no,
            "end_verso": end_no,
            "versi": [v["urn"] for v in chunk],
            "ssml": ssml
        })
        if i + block_size >= n:
            break
        i += step
    return blocks

def last_word(text: str) -> str:
    tokens = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ’']+", text)
    return (tokens[-1].lower() if tokens else "")

def rhyme_letter_for_terzina_local(idx_in_terzina: int) -> str:
    # a-b-a scheme locally
    return "aba"[idx_in_terzina]

def pipeline(pdf_path: str, cantica: str, canto: int, start_page: int, end_page: int,
             block_size: int = 12, block_overlap: int = 0) -> Dict[str, Any]:
    cantica_std = CANTICA_MAP.get(cantica.strip().lower(), cantica)
    lines = extract_lines_from_pdf(pdf_path, start_page, end_page)

    verses = []
    verse_counter = 1
    terzina_pos = 0  # 0,1,2
    for line in lines:
        urn = create_urn(cantica_std, canto, verse_counter)
        rl = rhyme_letter_for_terzina_local(terzina_pos)
        verses.append({
            "urn": urn,
            "number": verse_counter,
            "text_original": line,
            "last_word": last_word(line),
            "rhyme_letter": rl,
            "ssml": make_ssml_for_verso(line)
        })
        verse_counter += 1
        terzina_pos = (terzina_pos + 1) % 3

    terzine = group_terzine(verses)
    blocks = build_recitation_blocks(verses, block_size=block_size, overlap=block_overlap)

    payload = {
        "cantica": cantica_std,
        "canto": canto,
        "source": {"pdf": pdf_path, "pages": [start_page, end_page]},
        "counts": {"versi": len(verses), "terzine": len(terzine), "recitation_blocks": len(blocks)},
        "versi": verses,
        "terzine": terzine,
        "recitation_blocks": blocks
    }
    return payload

def main():
    ap = argparse.ArgumentParser(description="Estrai versi dal PDF Petrocchi e genera JSON con terzine e blocchi di recitazione.")
    ap.add_argument("--pdf", required=True, help="Percorso al PDF Petrocchi")
    ap.add_argument("--cantica", required=True, choices=["Inferno", "Purgatorio", "Paradiso", "inferno", "purgatorio", "paradiso"], help="Cantica")
    ap.add_argument("--canto", required=True, type=int, help="Numero del canto")
    ap.add_argument("--start-page", required=True, type=int, help="Pagina iniziale (1-based)")
    ap.add_argument("--end-page", required=True, type=int, help="Pagina finale (inclusa)")
    ap.add_argument("--block-size", type=int, default=12, help="Dimensione blocco recitativo (versi)")
    ap.add_argument("--block-overlap", type=int, default=0, help="Sovrapposizione tra blocchi (versi)")
    ap.add_argument("--output", required=True, help="Percorso file JSON di output")
    args = ap.parse_args()

    data = pipeline(
        pdf_path=args.pdf,
        cantica=args.cantica,
        canto=args.canto,
        start_page=args.start_page,
        end_page=args.end_page,
        block_size=args.block_size,
        block_overlap=args.block_overlap
    )
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"OK: salvato JSON → {args.output}")
    print(json.dumps(data["counts"], ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
