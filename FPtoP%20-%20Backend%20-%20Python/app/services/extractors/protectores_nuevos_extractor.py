import pandas as pd
from typing import Dict, List, Optional
from app.services.extractors.pdf_extractor_core import (procesar_pdf_generico, find_anchor)

def extraer_datos_protectores_nuevos(pdf_path: str):
    
    def estrategia_protectores_nuevos(df: pd.DataFrame) -> Optional[Dict[str, List]]:
        trazabilidad_info = find_anchor(df, "TRAZABILIDAD")
        if not trazabilidad_info:
            return None
        
        try:
            columna_ref = df.columns[trazabilidad_info["col_idx"] - 1]
            notes_row = -1
            for i in range(trazabilidad_info["fila"], len(df)):
                if "NOTAS" in str(df.loc[i, columna_ref]):
                    notes_row = i
                    break
            
            if notes_row == -1:
                return None
            
            headers_row = trazabilidad_info["fila"] + 1
            data_starts_row = trazabilidad_info["fila"] + 2
            data_ends_row = notes_row
            
        except (IndexError, KeyError):
            return None
        
        headers_to_search = [
            "ÍTEM", "DESCRIPCIÓN DE LA HERRAMIENTA O BIEN", "CANTIDAD", "NÚMEROS DE SERIE/MODELO",
            "NÚMERO DE LOTE", "FABRICANTE"
        ]
        
        headers_position = {}
        for col_name in df.columns:
            header = df.loc[headers_row, col_name]
            if pd.notna(header) and header.strip().upper() in [h.upper() for h in headers_to_search]:
                headers_position[header.strip().upper()] = col_name
        
        item_name_column = headers_position.get("ÍTEM")
        if not item_name_column:
            return None
        
        index_col_item = df.columns.get_loc(item_name_column)
        offset_column_indicator = df.columns[index_col_item - 1]
        
        result = {header: [] for header in headers_to_search}
        
        for i in range(data_starts_row, data_ends_row):
            offset = pd.notna(df.loc[i, offset_column_indicator])
            
            for header in headers_to_search:
                column_without_offset = headers_position.get(header.upper())
                if not column_without_offset:
                    result[header].append(None)
                    continue
                
                if offset:
                    normal_column_index = df.columns.get_loc(column_without_offset)
                    if normal_column_index > 0:
                        offset_column = df.columns[normal_column_index - 1]
                        value = df.loc[i, offset_column]
                    else:
                        value = None
                else:
                    value = df.loc[i, column_without_offset]
                
                result[header].append(value)
        
        normalized = {}
        for k, v in result.items():
            if k in ["DESCRIPCIÓN DE LA HERRAMIENTA O BIEN", "DESCRIPCIÓN"]:
                normalized["DESCRIPCIÓN"] = v
            elif k == "NÚMEROS DE SERIE/MODELO":
                normalized["NÚMERO DE SERIE/MODELO"] = v
            else:
                normalized[k.upper()] = v
        
        normalized.pop("ÍTEM", None)
        
        if "DESCRIPCIÓN" in normalized:
            num_descriptions = len(normalized["DESCRIPCIÓN"])
            normalized["CONDICIÓN"] = ["NUEVO"] * num_descriptions
        
        return normalized
    
    HEADERS_MAPPING = {
        "DESCRIPCIÓN": "DESCRIPCIÓN", "CANTIDAD": "CANTIDAD", "NÚMERO DE SERIE/MODELO": "NÚMERO DE SERIE/MODELO",
        "NÚMERO DE LOTE": "NÚMERO DE LOTE", "FABRICANTE": "FABRICANTE", "CONDICIÓN": "CONDICIÓN"
    }
    
    return procesar_pdf_generico(
        pdf_path=pdf_path,
        extraction_func=estrategia_protectores_nuevos,
        headers_mapping=HEADERS_MAPPING
    )