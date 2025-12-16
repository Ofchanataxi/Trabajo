import pandas as pd
from typing import Dict, List, Optional
from app.services.extractors.pdf_extractor_core import (
    procesar_pdf_generico, 
    find_anchor, 
    count_data_rows,
    extract_column_values
)
from app.services.data_cleaner import build_final_description, to_int_safe
from app.services.extractors.extractor_utils import clean_quantities, merge_descriptions

def extraer_datos_equipos_de_fondo(pdf_path: str):
    
    def estrategia_equipos_fondo(df: pd.DataFrame) -> Optional[Dict[str, List]]:
        # 1. Buscar ancla
        anchor_info = find_anchor(df, "DESCRIPCIÓN")
        if not anchor_info:
            return None
        
        # 2. Contar filas de datos
        num_rows = count_data_rows(df, anchor_info, allow_empty_streak=False)
        if num_rows == 0:
            return None
        
        # 3. Extraer columnas secuencialmente
        result = {}
        headers_order = [
            "DESCRIPCIÓN", "CANT.", "NUMERO DE SERIE", 
            "DESCRIPCIÓN", "ESTADO DEL EQUIPO", "OBSERVACIONES"
        ]
        
        for idx, header in enumerate(headers_order):
            col_idx = anchor_info["col_idx"] + idx
            if col_idx >= len(df.columns):
                break
            
            col_name = df.columns[col_idx]
            values = extract_column_values(df, col_name, anchor_info["fila"] + 1, num_rows)
            
            if header not in result:
                result[header] = []
            result[header].extend(values)
        
        # 4. Limpiar cantidades
        if "CANT." in result:
            result["CANT."] = clean_quantities(result["CANT."])
        
        # 5. Combinar descripciones
        if "DESCRIPCIÓN" in result:
            result["DESCRIPCIÓN"] = merge_descriptions(result["DESCRIPCIÓN"], num_rows)
        
        return result
    
    HEADERS_MAPPING = {
        "CANT.": "CANTIDAD",
        "DESCRIPCIÓN": "DESCRIPCIÓN",
        "NUMERO DE SERIE": "NÚMERO DE SERIE",
        "ESTADO DEL EQUIPO": "CONDICIÓN",
        "OBSERVACIONES": "OBSERVACIONES"
    }
    
    return procesar_pdf_generico(
        pdf_path=pdf_path,
        extraction_func=estrategia_equipos_fondo,
        headers_mapping=HEADERS_MAPPING
    )