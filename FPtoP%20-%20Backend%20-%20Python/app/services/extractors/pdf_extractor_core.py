import pandas as pd
from typing import Optional, Dict, List, Callable, Tuple, Literal
from app.services.extract_data_from_pdf import extract_data_from_pdf
from app.services.data_cleaner import clean_final_result
import re


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

def find_cell_position(
    df: pd.DataFrame, 
    anchor_text: str, 
    buscar_en_cabecera: bool = False 
) -> Optional[Tuple[int, int]]:
    """
    Busca el 'anchor_text'.
    - Si buscar_en_cabecera == True, busca en headers PRIMERO, luego en celdas.
    - Si buscar_en_cabecera == False, busca SÓLO en celdas.
    """
    if not anchor_text: return None
    try:
        search_pattern = re.compile(re.escape(str(anchor_text).strip()), re.IGNORECASE)
    except re.error as e:
        print(f"Error al compilar la regex para '{anchor_text}': {e}")
        return None

    if buscar_en_cabecera:
        for c, col_name in enumerate(df.columns):
            col_str = str(col_name).strip()
            if search_pattern.search(col_str):
                print(f"DEBUG: find_cell_position (cabecera=True) encontró '{anchor_text}' en el ENCABEZADO (col {c})")
                return (-1, c)  # Devuelve Fila = -1 (bandera especial)

    for r in range(df.shape[0]):
        for c in range(df.shape[1]):
            cell_value = df.iat[r, c]
            if pd.isna(cell_value):
                continue
            
            cell_str = str(cell_value).strip()
            
            if search_pattern.search(cell_str):
                print(f"DEBUG: find_cell_position (cabecera={buscar_en_cabecera}) encontró '{anchor_text}' en la CELDA ({r}, {c})")
                return (r, c)
    
    return None

def get_adjacent_value(
    df: pd.DataFrame, 
    anchor_text: str, 
    direction: Literal["right", "left", "above", "below", "inline"],
    buscar_en_cabecera: bool = False 
) -> Optional[str]:
    if not anchor_text or not direction:
        return None

    # 4. Pasamos el booleano a la función de búsqueda
    anchor_pos = find_cell_position(df, anchor_text, buscar_en_cabecera=buscar_en_cabecera)
    
    if anchor_pos is None:
        return None # No se encontró en ningún lado
        
    r, c = anchor_pos

    if direction == "inline":
        try:
            if r == -1: # Encontrado en ENCABEZADO
                value_str = str(df.columns[c])
            else: # Encontrado en CELDA
                value_str = str(df.iat[r, c])
            
            parts = re.split(r'[\r\n]+', value_str)
            parts = [p.strip() for p in parts if p.strip()]
            return parts[-1] if len(parts) > 1 else None
        except Exception as e:
            print(f"Error procesando valor 'inline' en ({r}, {c}): {e}")
            return None

    if r == -1: # Encontrado en ENCABEZADO
        try:
            if direction == "below":
                value = df.iat[0, c] # Valor en la primera fila (r=0)
            elif direction == "right":
                value = df.columns[c + 1] # Siguiente encabezado
            else: # 'left' y 'above' no son lógicos aquí
                return None
            return str(value) if pd.notna(value) else None
        except Exception as e:
            print(f"Error procesando adyacente de ENCABEZADO ({r}, {c}): {e}")
            return None
    
    target_r, target_c = r, c
    
    if direction == "right":
        target_c += 1
    elif direction == "left":
        target_c -= 1
    elif direction == "below":
        target_r += 1
    elif direction == "above":
        target_r -= 1
    else:
        print(f"Error: Dirección '{direction}' no válida.")
        return None
        
    max_rows, max_cols = df.shape
    if (0 <= target_r < max_rows) and (0 <= target_c < max_cols):
        try:
            value = df.iat[target_r, target_c]
            return str(value) if pd.notna(value) else None
        except Exception as e:
            print(f"Error inesperado al acceder a la celda ({target_r}, {target_c}): {e}")
            return None
    else:
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