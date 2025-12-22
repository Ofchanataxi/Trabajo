import pandas as pd
from tabulate import tabulate
from app.services import iterate_over_pdf_data
from app.services.unify_data import unify_blocks
from app.services.clean_data import data_cleaning

def ensure_dfs(data):
    if isinstance(data, pd.DataFrame):
        return [data]
    if isinstance(data, list):
        if all(isinstance(x, pd.DataFrame) for x in data):
            return data
        # lista de filas/valores -> conviértelo
        return [pd.DataFrame(data)]
    raise TypeError("Se esperaba DataFrame o lista de DataFrames")



def obtain_data_tally_tenaris(data: list[pd.DataFrame]):
    print("obtain_data_tally_tenaris")
    dfs = ensure_dfs(data)

    all_matches = []
    for i, df in enumerate(dfs):
        parts = iterate_over_pdf_data.extract_multi_blocks_by_repeated_headers(
            df,
            symbol_col_text="#",
            expected_headers=("#", "URC", "Pipe #", "Length", "Heat #", "Run. Length"),
            min_hits=3
        )
        # anota índice de origen para debug (si tu función no lo hace)
        for p in parts:
            p.setdefault("index", i)
        all_matches.extend(parts)

    if not all_matches:
        print("No se encontró la cabecera en ningún DataFrame.")
        return None

    # Debug/preview: imprime metadatos de cada bloque y primeras filas
    for j, m in enumerate(all_matches, 1):
        i = m.get("index", "?")
        print(f"\n=== Tabla {i} | subtabla {j} | header en {m['header_pos']} | cols {m['cols']} | rows {m['rows']} ===")
        try:
            print(tabulate(m["block"].head(20), headers="keys", tablefmt="fancy_grid", showindex=False))
        except Exception as e:
            print(f"(No se pudo tabular el bloque: {e})")

    # Si luego quieres unificar/limpiar:
    df_final = unify_blocks(all_matches)   
    df_final = data_cleaning(df_final)     
    print("\n=== BLOQUE UNIFICADO ===")
    print(tabulate(df_final, headers="keys", tablefmt="fancy_grid", showindex=False))

    return df_final  