import re
import pandas as pd

# --- FUNCIONES AUXILIARES DE LIMPIEZA Y NORMALIZACION DE DATOS---

def clean_final_result(data_dictionary: dict) -> dict:
    cleaned_dict = {}
    for key, values in data_dictionary.items():
        cleaned_values = []
        for value in values:
            if not isinstance(value, str):
                value = str(value)

            text = re.sub(r'[\r\n\t]', ' ', value)

            def dash_replacer(match):
                before, after = match.group(1), match.group(2)
                if before.isdigit() and after.isdigit():
                    return f"{before}-{after}"
                return f"{before} {after}"

            if key not in ["NUMERO DE SERIE", "NÚMERO DE SERIE/MODELO", "NÚMERO DE LOTE"]:
                text = re.sub(r'(.?)-(.?)', dash_replacer, text)

            parts = [part for part in text.split() if part != '/']
            cleaned_text = " ".join(parts).strip()

            if cleaned_text.upper() in ('N/A', '-', 'NA', 'NAN'):
                cleaned_text = ''

            if key.upper() in [
                "CANTIDAD", 
                "CANTIDAD DE ACCESORIOS RECIBIDOS POR EL PROVEEDOR", 
                "CANTIDAD DE ACCESORIOS REPARADOS OPERATIVOS"
            ]:
                if cleaned_text.isdigit():
                    cleaned_text = str(int(cleaned_text))
            cleaned_values.append(cleaned_text)
        cleaned_dict[key] = cleaned_values
    return remove_empty_data(cleaned_dict)

def remove_empty_data(data_dictionary: dict) -> dict:
    if not data_dictionary:
        return {}

    keys = list(data_dictionary.keys())
    try:
        rows = list(zip(*[data_dictionary[key] for key in keys]))
    except ValueError:
        return data_dictionary

    filtered_rows = [row for row in rows if any(row)]

    if not filtered_rows:
        return {key: [] for key in keys}

    filtered_columns = list(zip(*filtered_rows))
    result_dict = {key: list(column) for key, column in zip(keys, filtered_columns)}

    return result_dict

def to_int_safe(value):
    if pd.isna(value): return 0
    try:
        value_str = str(value).strip()
        if value_str in ["", "-", "N/A", "NA", "None"]: return 0
        return int(float(value_str))
    except:
        return 0

def clean_description(text):
    if '-' in text: text = text.split('-')[-1]
    if '(' in text: text = text.split('(')[0]
    return re.sub(r'[^a-zA-Z0-9\s/áéíóúÁÉÍÓÚüÜ-]', '', text).strip()

def build_final_description(desc1, desc2):
    desc1_cleaned = clean_description(desc1)
    desc2_cleaned = desc2.strip()
    if desc2_cleaned == '-': return f"{desc2_cleaned}"
    mapping = {"SELLOS": "PROTECTOR", "BOMBA": "PUMP", "MANEJADOR DE GAS": "AGH", "DESCARGA": "BODH", "TRANSFORMADOR": "TRANSFORMER", "MIDJOINTS CABLE":"MID JOINT"}
    for k, v in mapping.items():
        if desc1_cleaned.upper() == k:
            desc1_cleaned = v
            break
    if desc1_cleaned.upper() in ["ACCESORIOS", "ACCESORIO", "VARIADOR"]: return desc2_cleaned
    if "INTAKE-SEPARADOR DE GAS" in desc1.upper(): desc1_cleaned = "SEPARADOR DE GAS"
    if desc2_cleaned.lower().startswith(desc1_cleaned.lower()): return desc2_cleaned
    if desc1_cleaned.upper() == "SENSOR": return f"SENSOR {desc2_cleaned}"
    return f"{desc1_cleaned}: {desc2_cleaned}"

def norm_text(s: str) -> str:
    if pd.isna(s):
        return ""
    s = str(s).strip().upper()
    s = (s
         .replace("Á","A").replace("É","E").replace("Í","I").replace("Ó","O").replace("Ú","U"))
    s = re.sub(r"\s+", " ", s)
    return s