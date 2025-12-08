import pandas as pd
import numpy as np

def data_cleaning(df: pd.DataFrame) -> pd.DataFrame:
    """
    Limpieza completa de DataFrame para tablas de Tally Tenaris.
    - Normaliza tipos de columnas (#, URC, Pipe #, Length, Heat #)
    - Redondea decimales
    - Elimina duplicados exactos
    - Ordena por número de secuencia '#'
    - Reinicia índices
    """
    
    # 1️⃣ Copia segura
    df = df.copy()

    # 2️⃣ Normalización de nombres de columnas
    df.columns = [str(c).strip() for c in df.columns]

    # 3️⃣ Conversión de tipos
    if "#" in df.columns:
        df["#"] = pd.to_numeric(df["#"], errors="coerce")

    if "URC" in df.columns:
        df["URC"] = df["URC"].astype(str).str.strip()

    if "Pipe #" in df.columns:
        # Mantener los ceros a la izquierda
        df["Pipe #"] = df["Pipe #"].astype(str).str.strip().str.zfill(12)

    if "Length" in df.columns:
        df["Length"] = pd.to_numeric(df["Length"], errors="coerce").round(3)

    if "Heat #" in df.columns:
        df["Heat #"] = df["Heat #"].astype(str).str.strip()

    # 4️⃣ Eliminar filas totalmente vacías
    df = df.dropna(how="all")

    # 5️⃣ Eliminar duplicados exactos (todas las columnas)
    df = df.drop_duplicates(ignore_index=True)

    # 6️⃣ Eliminar duplicados por subconjunto clave
    subset_cols = [c for c in ["#", "URC", "Pipe #", "Length", "Heat #"] if c in df.columns]
    if subset_cols:
        df = df.drop_duplicates(subset=subset_cols, keep="first", ignore_index=True)

    # 7️⃣ Ordenar por número de secuencia
    if "#" in df.columns:
        df = df.sort_values(by="#", kind="stable", ignore_index=True)

    # 8️⃣ Limpieza final de espacios y NaNs residuales
    df = df.replace({np.nan: None})

    return df
