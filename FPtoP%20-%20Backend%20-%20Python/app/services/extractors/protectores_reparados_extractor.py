import pandas as pd
from typing import Dict, List, Optional
from app.services.extractors.pdf_extractor_core import (procesar_pdf_generico, find_anchor, count_data_rows, extract_column_values)
from app.services.data_cleaner import build_final_description, to_int_safe

def extraer_datos_protectores_reparados(pdf_path: str):
    def estrategia_protectores_reparados(df: pd.DataFrame) -> Optional[Dict[str, List]]:
        trazabilidad_info = find_anchor(df, "TRAZABILIDAD")
        if not trazabilidad_info:
            return None
        
        try:
            anchor_col_index = trazabilidad_info["col_idx"]
            col_ref = None
            
            for i in range(anchor_col_index - 1, -1, -1):
                col_candidate = df.columns[i]
                if pd.notna(df.loc[trazabilidad_info["fila"], col_candidate]):
                    col_ref = col_candidate
                    break
            
            if not col_ref:
                return None
            
            num_rows_nan = 0
            for i in range(trazabilidad_info["fila"] + 1, len(df)):
                if pd.isna(df.loc[i, col_ref]):
                    num_rows_nan += 1
                else:
                    break
            
            if num_rows_nan == 0:
                return None
                
        except (IndexError, KeyError):
            return None
        
        TARGET_HEADERS = ["MARCA PROTECTOR", "MEDIDA/ MODELO", "CANTIDAD", "CANT. REPARADOS OPERATIVOS"]
        result = {}
        finded_headers = set()
        
        for idx in range(anchor_col_index + 1, len(df.columns)):
            current_col = df.columns[idx]
            search_range = df[current_col].iloc[
                trazabilidad_info["fila"] + 1 : trazabilidad_info["fila"] + 1 + num_rows_nan
            ]
            
            for target_header in TARGET_HEADERS:
                if target_header in finded_headers:
                    continue
                
                header_cell = search_range[search_range.str.contains(target_header, na=False)]
                
                if not header_cell.empty:
                    header_index = header_cell.index[0]
                    
                    if target_header == "CANT. REPARADOS OPERATIVOS":
                        next_col = df.columns[idx + 1] if idx + 1 < len(df.columns) else None
                        values = []
                        for i in range(header_index + 1, trazabilidad_info["fila"] + num_rows_nan + 1):
                            if pd.notna(df.at[i, current_col]) or (next_col and pd.notna(df.at[i, next_col])):
                                v1 = to_int_safe(df.at[i, current_col])
                                v2 = to_int_safe(df.at[i, next_col]) if next_col else 0
                                values.append(v1 + v2)
                        result[target_header] = values
                    else:
                        values = []
                        for i, value in df[current_col].loc[
                            header_index + 1 : trazabilidad_info["fila"] + num_rows_nan
                        ].items():
                            if pd.notna(value):
                                values.append(value)
                        result[target_header] = values
                    
                    finded_headers.add(target_header)
                    break

        if result and "MEDIDA/ MODELO" in result:
            num_descriptions = len(result["MEDIDA/ MODELO"])
            result["CONDICIÓN"] = ["REPARADO"] * num_descriptions
        
        return result
    
    HEADERS_MAPPING = {
        "MARCA PROTECTOR": "FABRICANTE", "MEDIDA/ MODELO": "DESCRIPCIÓN", "CANTIDAD": "CANTIDAD DE ACCESORIOS RECIBIDOS POR EL PROVEEDOR",
        "CANT. REPARADOS OPERATIVOS": "CANTIDAD DE ACCESORIOS REPARADOS OPERATIVOS", "CONDICIÓN": "CONDICIÓN"
    }
    
    return procesar_pdf_generico(
        pdf_path=pdf_path,
        extraction_func=estrategia_protectores_reparados,
        headers_mapping=HEADERS_MAPPING
    )