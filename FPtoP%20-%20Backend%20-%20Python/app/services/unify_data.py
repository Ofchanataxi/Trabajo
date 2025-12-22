import pandas as pd
import re

# 1) Normalizar encabezados a un esquema canónico
CANON = {
    "#": "#",
    "URC": "URC",
    "PIPE#": "Pipe #",
    "PIPE": "Pipe #",
    "LENGTH": "Length",
    "HEAT#": "Heat #",
    "HEAT": "Heat #",
    "RUN.LENGTH": "Run. Length",
    "RUNLENGTH": "Run. Length",
}

def _canonize(colname: str) -> str:
    if not isinstance(colname, str):
        return colname
    key = re.sub(r"[^a-z0-9#]+", "", colname.lower())  # quita espacios, puntos
    key = key.upper()
    return CANON.get(key, colname)  # si no mapea, deja como está

def _to_float_comma(x):
    if pd.isna(x): return pd.NA
    s = str(x).strip()
    if s == "" or s.lower() == "nan": return pd.NA
    # Convierte "31,709" -> 31.709 (float)
    s = s.replace(".", "") if re.search(r"\d\.\d{3}(,|$)", s) else s  # quita separador de miles si viniera con punto
    s = s.replace(",", ".")
    try:
        return float(s)
    except:
        return pd.NA

def _to_int_safe(x):
    if pd.isna(x): return pd.NA
    s = str(x).strip()
    if not s or not re.fullmatch(r"\d+", s):
        return pd.NA
    try:
        return int(s)
    except:
        return pd.NA

def unify_blocks(matches: list[dict]) -> pd.DataFrame:
    frames = []
    for m in matches:
        df = m["block"].copy()

        # 1) canonizar encabezados
        df.columns = [_canonize(c) for c in df.columns]

        # 2) quitar filas de totales/resumen y filas totalmente vacías
        #    (ej.: 'Pieces', 'Total' que te salen en la primera col)
        df = df.dropna(how="all")
        if "#" in df.columns:
            mask_bad = df["#"].astype(str).str.fullmatch(r"(?i)total|pieces|nan|\s*")
            df = df[~mask_bad]

        # 3) asegurar que existan todas las columnas esperadas (por si alguna subtabla vino incompleta)
        expected = ["#", "URC", "Pipe #", "Length", "Heat #", "Run. Length"]
        for col in expected:
            if col not in df.columns:
                df[col] = pd.NA
        df = df[expected]  # reordenar

        # 4) normalizar tipos
        df["#"] = df["#"].apply(_to_int_safe)
        df["Length"] = df["Length"].apply(_to_float_comma)
        df["Run. Length"] = df["Run. Length"].apply(_to_float_comma)

        frames.append(df)

    if not frames:
        return pd.DataFrame(columns=["#", "URC", "Pipe #", "Length", "Heat #", "Run. Length"])

    out = pd.concat(frames, ignore_index=True)
    out = out.sort_values(
        by=[out.columns[0]],  
        kind="stable",
        ignore_index=True
    )

    return out
