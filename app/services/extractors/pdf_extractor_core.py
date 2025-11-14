import pandas as pd
from typing import Optional, Dict, List, Callable
from app.services.extract_data_from_pdf import extract_data_from_pdf
from app.services.data_cleaner import clean_final_result


def procesar_pdf_generico(
    pdf_path: str,
    extraction_func: Callable[[pd.DataFrame], Optional[Dict[str, List]]],
    headers_mapping: dict
) -> Optional[Dict[str, List]]:
    tables = extract_data_from_pdf(pdf_path)
    
    if not tables:
        print("⚠️ No se detectaron tablas en el PDF.")
        return None
    
    # Intentar extraer de cada tabla
    for df in tables:
        # Llamar a la función de extracción personalizada
        extracted_data = extraction_func(df)
        
        if extracted_data and any(extracted_data.values()):
            # Aplicar mapeo de headers
            mapped_result = {}
            for original_key, normalized_key in headers_mapping.items():
                if original_key in extracted_data:
                    mapped_result[normalized_key] = extracted_data[original_key]
            
            # Limpiar y retornar
            return clean_final_result(mapped_result)
    
    return None

def find_anchor(df: pd.DataFrame, keyword: str) -> Optional[Dict[str, int]]:
    for col_name in df.columns:
        if df[col_name].astype(str).str.contains(keyword, na=False).any():
            anchor_row = df[df[col_name].astype(str).str.contains(keyword, na=False)].index[0]
            col_idx = df.columns.get_loc(col_name)
            return {"fila": anchor_row, "col_idx": col_idx}
    return None


def count_data_rows(df: pd.DataFrame, anchor_info: Dict[str, int], 
                   allow_empty_streak: bool = False) -> int:
    col_anchor = df.columns[anchor_info["col_idx"]]
    num_rows_data = 0
    empty_streak = 0
    
    for i in range(anchor_info["fila"] + 1, len(df)):
        cell_value = df[col_anchor].iloc[i]
        is_empty = pd.isna(cell_value) or str(cell_value).strip() == ""
        
        if is_empty:
            if allow_empty_streak:
                empty_streak += 1
                if empty_streak >= 2:
                    break
            else:
                break
        else:
            empty_streak = 0
            num_rows_data += 1
    
    return num_rows_data


def extract_column_values(df: pd.DataFrame, col_name: str, 
                         start_row: int, num_rows: int) -> List:
    return df[col_name].iloc[start_row:start_row + num_rows].tolist()