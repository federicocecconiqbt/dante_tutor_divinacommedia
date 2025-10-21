#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import json
import argparse
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

try:
    import PyPDF2
except ImportError:
    raise SystemExit("PyPDF2 mancante. Installa con: pip install PyPDF2")

# ------------------------ Configurazione pattern ------------------------

CANTICHE_TITLES = {
    "INFERNO": "Inferno",
    "PURGATORIO": "Purgatorio",
    "PARADISO": "Paradiso",
}

# Canto headings tipici tipo "CANTO PRIMO", "CANTO TRENTESIMOTERZO", ecc.
CANTO_HEADER_RE = re.compile(r"^\s*CANTO\s+[A-ZÀÈÉÌÒÙ]+(\s+[A-ZÀÈÉÌÒÙ]+)?\s*$")

# Sovente gli header hanno la singola parola "INFERNO" ecc. su una riga.
CANTICA_HEADER_RE = re.compile(r"^\s*(INFERNO|PURGATORIO|PARADISO)\s*$", re.IGNORECASE)

# Filtri di header/footer e rumore comune (paginazione, cornici, didascalie generiche)
HEADER_PATTERNS = [
    r"^\s*LA\s+DIVINA\s+COMMEDIA\s*$",
    r"^\s*DANTE\s+ALIGHIERI\s*$",
    r"^\s*Propriet[aà]\s+letteraria.*$",
    r"^\s*Milano\.\s*–\s*Tip\.\s*Treves\.\s*$",
    r"^\s*PREFAZIONE\s*$",
    r"^\s*INDICE.*$",
    r"^\s*Liber\s+Liber\s*$",
]

FOOTER_PATTERNS = [
    r"^\s*\d+\s*$",  # soli numeri pagina
]

ILLUSTRATION_PATTERNS = [
    r"^\s*Raffaello\..*$",
    r"^\s*Michelangelo\..*$",
    r"^\s*Luca\s+Signorelli\..*$",
    r"^\s*Disegno\s+di\s+.*$",
    r"^\s*Miniatura\s+del\s+.*$",
    r"^\s*Pagina\s+del\s+Dante.*$",
]

def looks_like_noise(line: str) -> bool:
    for pat in HEADER_PATTERNS + FOOTER_PATTERNS + ILLUSTRATION_PATTERNS:
        if re.match(pat, line, flags=re.IGNORECASE):
            return True
    return False

def clean_line(line: str) -> str:
    line = line.replace("\u00ad", "")  # soft hyphen
    line = line.replace("’", "’")      # keep smart apostrophe as-is
    return line.strip()

def is_probable_verse(line: str) -> bool:
    if not line:
        return False
    if looks_like_noise(line):
        return False
    # Evita titoli/capoversi in maiuscoletto brevi
    if re.match(r"^[A-Z\s\.\-]+$", line) and len(line.split()) <= 4:
        # ma consenti CANTO ... che gestiamo a parte
        if not CANTO_HEADER_RE.match(line) and not CANTICA_HEADER_RE.match(line):
            return False
    # righe-titolo tipo "CANTO PRIMO" sono gestite altrove, non come versi
    if CANTO_HEADER_RE.match(line) or CANTICA_HEADER_RE.match(line):
        return False
    # Evita righe di pura punteggiatura o molto corte
    if len(re.sub(r"\W+", "", line)) < 2:
        return False
    return True

def last_word(text: str) -> str:
    tokens = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ’']+", text)
    return (tokens[-1].lower() if tokens else "")

def short_cantica(cantica: str) -> str:
    c = cantica.strip().lower()
    if c.startswith("inf"):
        return "inf"
    if c.startswith("pur"):
        return "purg"
    if c.startswith("par"):
        return "par"
    raise ValueError(f"Cantica non riconosciuta: {cantica}")

def verse_urn(cantica: str, canto: int, n: int) -> str:
    return f"{short_cantica(cantica)}.{int(canto):02d}.{int(n):03d}"

def ssml_for_verso(text: str) -> str:
    safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f"<s>{safe}</s>"

def ssml_block(verses_texts: List[str]) -> str:
    parts = []
    for i, t in enumerate(verses_texts, start=1):
        parts.append(f"<s>{t}</s>")
        parts.append("<break time='220ms'/>" if i % 3 == 0 else "<break time='120ms'/>")
    return f"<p>{''.join(parts)}</p>"

def group_terzine(verses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for i in range(0, len(verses), 3):
        chunk = verses[i:i+3]
        if len(chunk) < 3:
            break
        start_no = chunk[0]["number"]
        end_no = chunk[-1]["number"]
        out.append({
            "urn": f"{chunk[0]['urn'][:-3]}{start_no:03d}-{end_no:03d}",
            "start_verso": start_no,
            "end_verso": end_no,
            "rhyme_scheme": "aba",  # semplificazione locale
            "versi": [v["urn"] for v in chunk]
        })
    return out

def make_blocks(verses: List[Dict[str, Any]], size: int, overlap: int) -> List[Dict[str, Any]]:
    if size <= 0:
        return []
    blocks = []
    step = max(1, size - overlap)
    i = 0
    n = len(verses)
    while i < n:
        chunk = verses[i:i+size]
        if not chunk:
            break
        start_no = chunk[0]["number"]
        end_no = chunk[-1]["number"]
        ssml = ssml_block([c["text_original"] for c in chunk])
        blocks.append({
            "urn": f"{chunk[0]['urn'][:-3]}{start_no:03d}-{end_no:03d}",
            "start_verso": start_no,
            "end_verso": end_no,
            "versi": [v["urn"] for v in chunk],
            "ssml": ssml
        })
        if i + size >= n:
            break
        i += step
    return blocks

@dataclass
class CantoBuffer:
    cantica: str
    canto_num: int
    verses: List[Dict[str, Any]] = field(default_factory=list)

    def add_verse(self, text: str):
        n = len(self.verses) + 1
        self.verses.append({
            "urn": verse_urn(self.cantica, self.canto_num, n),
            "number": n,
            "text_original": text,
            "last_word": last_word(text),
            "rhyme_letter": "aba"[(n - 1) % 3],  # a-b-a locale
            "ssml": ssml_for_verso(text),
        })

    def to_json(self, source_pdf: str, pages_range: List[int], block_size: int, block_overlap: int) -> Dict[str, Any]:
        terzine = group_terzine(self.verses)
        blocks = make_blocks(self.verses, size=block_size, overlap=block_overlap)
        return {
            "cantica": self.cantica,
            "canto": self.canto_num,
            "source": {"pdf": source_pdf, "pages": pages_range},
            "counts": {"versi": len(self.verses), "terzine": len(terzine), "recitation_blocks": len(blocks)},
            "versi": self.verses,
            "terzine": terzine,
            "recitation_blocks": blocks
        }

def parse_pdf(pdf_path: str) -> List[List[str]]:
    pages_lines: List[List[str]] = []
    with open(pdf_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for p in range(len(reader.pages)):
            text = reader.pages[p].extract_text() or ""
            lines = [clean_line(x) for x in text.splitlines() if clean_line(x)]
            pages_lines.append(lines)
    return pages_lines

def run_pipeline(pdf: str, outdir: str, block_size: int, block_overlap: int) -> Dict[str, Any]:
    os.makedirs(outdir, exist_ok=True)
    pages_lines = parse_pdf(pdf)

    manifest: Dict[str, Any] = {
        "pdf": pdf,
        "outdir": outdir,
        "canti": []
    }

    current_cantica: Optional[str] = None
    current_canto_num: Optional[int] = None
    canto_buf: Optional[CantoBuffer] = None
    canto_start_page: Optional[int] = None

    def close_canto(end_page_idx: int):
        nonlocal canto_buf, current_cantica, current_canto_num, canto_start_page
        if canto_buf is None:
            return
        data = canto_buf.to_json(pdf, [ (canto_start_page or 0) + 1, end_page_idx + 1 ], block_size, block_overlap)
        fname = f"{short_cantica(current_cantica)}_{canto_buf.canto_num:02d}.json"
        fpath = os.path.join(outdir, fname)
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        manifest["canti"].append({"cantica": current_cantica, "canto": current_canto_num, "file": fpath, "counts": data["counts"]})
        canto_buf = None
        current_canto_num = None
        canto_start_page = None

    for page_idx, lines in enumerate(pages_lines):
        for line in lines:
            if CANTICA_HEADER_RE.match(line):
                close_canto(page_idx - 1)
                title = CANTICA_HEADER_RE.match(line).group(1).upper()
                current_cantica = CANTICHE_TITLES[title]
                continue

            if CANTO_HEADER_RE.match(line):
                if current_cantica is None:
                    continue
                close_canto(page_idx - 1)
                next_num = 1 if manifest.get(f"__last_canto_{current_cantica}") is None else manifest[f"__last_canto_{current_cantica}"] + 1
                manifest[f"__last_canto_{current_cantica}"] = next_num
                current_canto_num = next_num
                canto_buf = CantoBuffer(current_cantica, current_canto_num)
                canto_start_page = page_idx
                continue

            if canto_buf is not None and is_probable_verse(line):
                canto_buf.add_verse(line)

    close_canto(len(pages_lines) - 1)

    for k in list(manifest.keys()):
        if k.startswith("__last_canto_"):
            del manifest[k]

    manifest_path = os.path.join(outdir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    return {"manifest": manifest_path, "count_canti": len(manifest["canti"])}

def main():
    ap = argparse.ArgumentParser(description="Divina Commedia Petrocchi PDF -> JSON per tutta l'opera")
    ap.add_argument("--pdf", required=True, help="Percorso al PDF (ed. Petrocchi)")
    ap.add_argument("--outdir", required=True, help="Directory di output per i JSON")
    ap.add_argument("--block-size", type=int, default=12, help="Dimensione blocco recitazione (versi)")
    ap.add_argument("--block-overlap", type=int, default=0, help="Sovrapposizione blocchi (versi)")
    args = ap.parse_args()

    res = run_pipeline(args.pdf, args.outdir, args.block_size, args.block_overlap)
    print(json.dumps(res, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
