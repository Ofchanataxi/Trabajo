import re
import pandas as pd
from tabulate import tabulate
import unicodedata
from typing import Iterable, Dict, List, Optional, Tuple

# --------- Limpieza básica (opcional pero recomendado) ---------
def clean_df(df: pd.DataFrame) -> pd.DataFrame:
    # quita columnas totalmente vacías y 'Unnamed'
    df = df.loc[:, df.notna().any(axis=0)]
    df = df.loc[:, ~df.columns.astype(str).str.match(r'^Unnamed', na=False)]
    # aplana whitespace en todas las celdas
    return df.applymap(lambda x: re.sub(r'\s+', ' ', str(x)).strip() if pd.notna(x) else x)

# --- Normalizador robusto (espacios, NBSP, ancho completo, etc.) ---
def _norm(s: str) -> str:
    if not isinstance(s, str):
        return ""
    s = unicodedata.normalize("NFKC", s)         # normaliza unicode
    s = s.replace("\u00A0", " ")                 # NBSP -> espacio normal
    s = " ".join(s.split())                      # colapsa espacios
    return s.strip()

# --- ¿La celda coincide EXACTA (ignorando espacios/unicode)? ---
def _eq(cell, text: str) -> bool:
    return _norm(cell) == _norm(text)

# --- helpers genéricos para alias ---
def _acceptable_symbols(symbol_col_text: str, symbol_aliases: Optional[Iterable[str]]) -> set:
    acc = {_norm(symbol_col_text)}
    if symbol_aliases:
        acc |= {_norm(s) for s in symbol_aliases}
    return acc

def _acceptable_headers(expected_headers: Iterable[str], header_aliases: Optional[Dict[str, Iterable[str]]]) -> set:
    acc = set(_norm(h) for h in expected_headers)
    if header_aliases:
        for canon, alist in header_aliases.items():
            if _norm(canon) in acc:
                acc |= {_norm(a) for a in alist}
    return acc

def _aliases_for_sequence(expected_headers_seq: Iterable[str], header_aliases: Optional[Dict[str, Iterable[str]]]) -> List[set]:
    seq_sets: List[set] = []
    for h in expected_headers_seq:
        s = {_norm(h)}
        if header_aliases and h in header_aliases:
            s |= {_norm(a) for a in header_aliases[h]}
        seq_sets.append(s)
    return seq_sets

# --- Detecta la fila de cabeceras basada en "criterios fuertes" ---
def find_strict_header_row(
    df: pd.DataFrame,
    symbol_col_text: str = "#",
    expected_headers: Iterable[str] = ("URC", "Pipe #", "Length", "Heat #", "Run. Length"),
    min_hits: int = 3,
    *,
    header_aliases: Optional[Dict[str, Iterable[str]]] = None,
    symbol_aliases: Optional[Iterable[str]] = None
):
    """
    Busca la fila que:
      a) tenga una celda igual a symbol_col_text o a alguno de sus alias
      b) en esa misma fila existan al menos min_hits headers (canónicos o alias)
    Devuelve (row_idx, col_idx_del_symbol) o None si no encuentra.
    """
    exp_norm = _acceptable_headers(expected_headers, header_aliases)
    sym_norm = _acceptable_symbols(symbol_col_text, symbol_aliases)

    for r in range(len(df)):
        row_vals = df.iloc[r].tolist()
        row_norm = [_norm(v) for v in row_vals]

        # a) símbolo (o alias) presente en la fila
        try:
            col_symbol = next(i for i, v in enumerate(row_norm) if v in sym_norm)
        except StopIteration:
            continue

        # b) número de headers esperados/alias en la fila
        hits = sum(1 for v in row_norm if v in exp_norm)
        if hits >= min_hits:
            return (r, col_symbol)

    return None

def find_all_symbol_positions_in_row(
    df,
    row_idx: int,
    symbol_text: str = "#",
    *,
    symbol_aliases: Optional[Iterable[str]] = None
):
    """Devuelve todas las columnas en la fila row_idx donde la celda coincide con símbolo o sus alias (normalizados)."""
    from typing import List
    positions: List[int] = []
    row_vals = df.iloc[row_idx].tolist()
    acceptable = _acceptable_symbols(symbol_text, symbol_aliases)
    for c, v in enumerate(row_vals):
        if _norm(v) in acceptable:
            positions.append(c)
    return positions

def infer_span_end(
    df,
    header_row: int,
    start_col: int,
    expected_headers: Iterable[str],
    max_lookahead: int = 40,
    *,
    header_aliases: Optional[Dict[str, Iterable[str]]] = None
):
    """
    A partir de start_col (donde está el símbolo), intenta encontrar el final del set de cabecera.
    Busca los headers en orden (aceptando alias) y permite columnas intermedias.
    Devuelve (end_col_inclusive, headers_encontrados_list) o (None, None) si no cuadra.
    """
    exp_sets = _aliases_for_sequence(expected_headers, header_aliases)
    row_vals = [_norm(v) for v in df.iloc[header_row].tolist()]

    found_vals: List[str] = []
    c = start_col
    e = min(len(row_vals), start_col + max_lookahead)
    exp_idx = 0
    last_hit_col = start_col

    while c < e and exp_idx < len(exp_sets):
        val = row_vals[c]
        if val in exp_sets[exp_idx]:
            found_vals.append(val)
            last_hit_col = c
            exp_idx += 1
        c += 1

    if len(found_vals) >= max(3, len(exp_sets) - 1):  # flexible: acepta si encontró casi todos
        return last_hit_col, found_vals
    return None, None

def extract_multi_blocks_by_repeated_headers(
    df: pd.DataFrame,
    symbol_col_text: str = "#",
    expected_headers: Iterable[str] = ("#", "URC", "Pipe #", "Length", "Heat #", "Run. Length"),
    min_hits: int = 3,
    *,
    header_aliases: Optional[Dict[str, Iterable[str]]] = None,
    symbol_aliases: Optional[Iterable[str]] = None
):
    """
    Detecta la fila “fuerte” de cabeceras y, dentro de esa fila, todas las ocurrencias del símbolo.
    Para cada ocurrencia, infiere el span de columnas del set y extrae su bloque vertical.
    Devuelve una lista de dicts: [{"header_pos": (hr, hc), "cols": (c1,c2), "rows": (r1,r2), "block": df}, ...]
    """
    # 1) Encuentra fila de cabeceras fuerte
    pos = find_strict_header_row(
        df, symbol_col_text, expected_headers=tuple(expected_headers)[1:], min_hits=min_hits,
        header_aliases=header_aliases, symbol_aliases=symbol_aliases
    )
    if not pos:
        return []
    hr, _ = pos

    # 2) Todas las posiciones del símbolo
    symbol_cols = find_all_symbol_positions_in_row(df, hr, symbol_col_text, symbol_aliases=symbol_aliases)
    if not symbol_cols:
        return []

    results = []
    for hc in symbol_cols:
        # 3) Infierve el fin del span de cabecera para este set
        end_col, found_headers = infer_span_end(
            df, hr, hc, expected_headers, header_aliases=header_aliases
        )
        if end_col is None:
            # fallback: asume ancho igual al número de headers esperados - 1
            end_col = min(hc + len(tuple(expected_headers)) - 1, df.shape[1] - 1)

        c1, c2 = hc, end_col

        # 4) Delimitar filas hacia abajo
        start_row = hr + 1
        for r in range(start_row, len(df)):
            seg = df.iloc[r, c1:c2+1]
            if seg.isna().all() or (seg.astype(str).apply(_norm) == "").all():
                end_row = r - 1
                break
        else:
            end_row = len(df) - 1

        if end_row < start_row:
            continue

        block = df.iloc[start_row:end_row+1, c1:c2+1].copy()
        headers = df.iloc[hr, c1:c2+1].astype(str).map(_norm).tolist()
        block.columns = headers

        results.append({
            "header_pos": (hr, hc),
            "cols": (c1, c2),
            "rows": (start_row, end_row),
            "block": block
        })

    return results

# --- Extractor que usa la detección estricta de la cabecera ---
def extract_block_by_strict_header(
    df: pd.DataFrame,
    symbol_col_text: str = "#",
    expected_headers: Iterable[str] = ("URC", "Pipe #", "Length", "Heat #", "Run. Length"),
    min_hits: int = 3,
    *,
    header_aliases: Optional[Dict[str, Iterable[str]]] = None,
    symbol_aliases: Optional[Iterable[str]] = None
):
    pos = find_strict_header_row(
        df, symbol_col_text, expected_headers, min_hits,
        header_aliases=header_aliases, symbol_aliases=symbol_aliases
    )
    if not pos:
        return None
    hr, hc = pos

    c1 = hc
    last_non_empty = c1
    row_vals = [_norm(v) for v in df.iloc[hr].tolist()]
    for c in range(c1, len(row_vals)):
        if row_vals[c] != "":
            last_non_empty = c
    c2 = last_non_empty

    start_row = hr + 1
    for r in range(start_row, len(df)):
        seg = df.iloc[r, c1:c2+1]
        if seg.isna().all() or (seg.astype(str).apply(_norm) == "").all():
            end_row = r - 1
            break
    else:
        end_row = len(df) - 1

    block = df.iloc[start_row:end_row+1, c1:c2+1].copy()
    headers = df.iloc[hr, c1:c2+1].astype(str).map(_norm).tolist()
    block.columns = headers

    return {
        "header_pos": (hr, hc),
        "cols": (c1, c2),
        "rows": (start_row, end_row),
        "block": block,
    }

def find_header_exact(df: pd.DataFrame, header_text: str = "#"):
    # corregido: usar _norm (mismo nombre que arriba)
    target = _norm(header_text)
    for r in range(len(df)):
        for c in range(len(df.columns)):
            v = df.iat[r, c]
            if isinstance(v, str) and _norm(v) == target:
                return (r, c)
    return None

# --------- 1) Buscar la posición del primer header ---------
def find_header_pos(df: pd.DataFrame, keyword: str = "DESCRIPCION"):
    """
    Devuelve la primera posición (fila, columna) donde el contenido de la celda
    coincide exactamente con 'keyword' (ignorando espacios y mayúsculas).
    """
    kw = keyword.strip().upper()

    for r in range(len(df)):
        for c in range(len(df.columns)):
            val = df.iat[r, c]
            if isinstance(val, str) and val.strip().upper() == kw:
                return (r, c)
    return None

# --------- 2) Delimitar columnas del bloque hacia la derecha ---------
def find_block_cols(df: pd.DataFrame, header_row: int, start_col: int, keyword: str = "DESCRIPCION"):
    kw = keyword.upper()
    # busca el siguiente header igual en la misma fila; si no hay, usa última columna
    for c in range(start_col + 1, len(df.columns)):
        v = df.iat[header_row, c]
        if isinstance(v, str) and kw in v.upper():
            return (start_col, c - 1)
    return (start_col, len(df.columns) - 1)

# --------- 3) Delimitar filas del bloque hacia abajo ---------
def row_slice_is_empty(df: pd.DataFrame, row: int, c1: int, c2: int) -> bool:
    s = df.iloc[row, c1:c2+1]
    # vacío si todo es NaN o strings vacíos/espacios
    return s.isna().all() or (s.astype(str).str.strip() == '').all()

def find_block_rows(df: pd.DataFrame, header_row: int, c1: int, c2: int):
    start_row = header_row + 1
    for r in range(start_row, len(df)):
        if row_slice_is_empty(df, r, c1, c2):
            return (start_row, r - 1)
    return (start_row, len(df) - 1)

# ---------- buscar en VARIOS DataFrames ----------
def extract_block(
    dfs: list[pd.DataFrame],
    symbol_col_text: str = "#",
    expected_headers: Iterable[str] = ("#", "URC", "Pipe #", "Length", "Heat #", "Run. Length"),
    min_hits: int = 3,
    stop_at_first: bool = False,
    *,
    header_aliases: Optional[Dict[str, Iterable[str]]] = None,
    symbol_aliases: Optional[Iterable[str]] = None
):
    results = []
    for i, df in enumerate(dfs):
        parts = extract_multi_blocks_by_repeated_headers(
            df, symbol_col_text, expected_headers, min_hits,
            header_aliases=header_aliases, symbol_aliases=symbol_aliases
        )
        for p in parts:
            p["index"] = i
            results.append(p)
            if stop_at_first:
                return results
    return results

# ---------- helper para imprimir en CMD ----------
def print_block(block_df: pd.DataFrame, rows: int = 30, style: str = 'fancy_grid'):
    print(tabulate(block_df.head(rows), headers='keys', tablefmt=style, showindex=False, maxcolwidths=None))

# --------- 4) Extraer bloque a partir de un header ---------
# def extract_block(df: pd.DataFrame, keyword: str = "DESCRIPCION") -> pd.DataFrame | None:
#     # df = DataFrame que te dio Tabula
#     block = extract_block_by_strict_header(
#         df,
#         symbol_col_text="#",
#         expected_headers=("URC", "Pipe #", "Length", "Heat #", "Run. Length"),
#         min_hits=3
#     )
#
#     if block is None:
#         print("No encontré la fila de cabeceras reales (#, URC, Pipe #, ...).")
#     else:
#         from tabulate import tabulate
#         print(tabulate(block.head(30), headers='keys', tablefmt='fancy_grid', showindex=False, maxcolwidths=None))
#
#     return block

# --------- 5) (Opcional) Extraer TODOS los bloques si hay varios headers en la hoja ---------
def find_all_header_positions(df: pd.DataFrame, keyword: str = "DESCRIPCION"):
    kw = keyword.upper()
    pos = []
    for r in range(len(df)):
        for c in range(len(df.columns)):
            v = df.iat[r, c]
            if isinstance(v, str) and kw in v.upper():
                pos.append((r, c))
    return pos

def extract_all_blocks(df: pd.DataFrame, keyword: str = "DESCRIPCION"):
    blocks = []
    for (hr, hc) in find_all_header_positions(df, keyword):
        c1, c2 = find_block_cols(df, hr, hc, keyword)
        r1, r2 = find_block_rows(df, hr, c1, c2)
        blocks.append(df.iloc[r1:r2+1, c1:c2+1].copy())
    return blocks

# --------- 6) Mostrar en CMD con tabulate ---------
def print_block(block: pd.DataFrame, rows: int = 50, style: str = 'fancy_grid'):
    print(tabulate(block.head(rows), headers='keys', tablefmt=style, showindex=False, maxcolwidths=None, disable_numparse=True))
