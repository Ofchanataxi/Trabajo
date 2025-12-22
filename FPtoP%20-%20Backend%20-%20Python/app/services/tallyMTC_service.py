import tempfile
import os
import pandas as pd
from fastapi import UploadFile
from typing import List, Dict, Any
from fastapi.concurrency import run_in_threadpool
from app.services.extract_data_from_pdf import extract_data_from_pdf
from app.services.tally_tenaris import config_tally_tenaris 
from app.services.extractors.mtc_extractor import extraer_steel_grade_de_mtc
from app.services.extractors.pdf_extractor_core import get_adjacent_value

def _proceso_interno(path_tally: str, files_info_mtc: List[tuple]) -> pd.DataFrame:
    data_raw = extract_data_from_pdf(path_tally, lattice=True)
    if not data_raw:
        raise ValueError("No se pudieron extraer tablas del Tally PDF.")

    tally_df = config_tally_tenaris.obtain_data_tally_tenaris(data_raw)
    
    if not isinstance(tally_df, pd.DataFrame) or tally_df.empty:
        raise ValueError("El procesamiento del Tally no devolvió datos válidos.")

    descripcion_material = ""
    for df in data_raw:
        val = get_adjacent_value(df, anchor_text="Material Description", direction="below")
        if val:
            descripcion_material = val
            break

    tally_df["description"] = descripcion_material
    tally_df["quantity"] = 1
    
    columna_colada = "Heat #"
    if columna_colada not in tally_df.columns:
        raise ValueError(f"Columna '{columna_colada}' no encontrada en el Tally.")

    coladas_a_buscar = tally_df[columna_colada].astype(str).unique().tolist()
    
    # Diccionario para buscar información
    mapa_resultados = {}
    if coladas_a_buscar:
        mapa_resultados = extraer_steel_grade_de_mtc(files_info_mtc, coladas_a_buscar)

    # --- LÓGICA DE MAPEO DE DATOS ---
    
    # 1. Mapear Steel Grade
    tally_df['Steel Grade'] = tally_df[columna_colada].astype(str).map(
        lambda x: mapa_resultados.get(x, {}).get("grade", "No encontrado")
    )

    # 2. Mapear Archivo MTC
    tally_df['mtcFilename'] = tally_df[columna_colada].astype(str).map(
        lambda x: mapa_resultados.get(x, {}).get("file", "-")
    )

    # 3. Mapear y Concatenar "Tubing" o "Casing" a la descripción
    # Definimos una función para aplicar fila por fila
    def actualizar_descripcion(row):
        colada = str(row[columna_colada])
        info_mtc = mapa_resultados.get(colada, {})
        tipo_producto = info_mtc.get("product_type", "").upper()
        desc_actual = str(row["description"])

        # Si encontramos el tipo, lo concatenamos al inicio si no existe ya
        prefix = ""
        if "TUBING" in tipo_producto:
            prefix = "Tubing "
        elif "CASING" in tipo_producto:
            prefix = "Casing "
        
        # Evitar duplicar si la descripción ya empieza con eso
        if prefix and not desc_actual.upper().startswith(prefix):
            return prefix + desc_actual
        
        return desc_actual

    # Aplicamos la función si hay resultados
    if mapa_resultados:
        tally_df['description'] = tally_df.apply(actualizar_descripcion, axis=1)

    # --- AGRUPACIÓN ---
    agg_dict = {
        "quantity": "sum",
        "Steel Grade": "first",
        "mtcFilename": "first"
    }
    
    if "Length" in tally_df.columns:
        agg_dict["Length"] = "sum"

    # Agrupamos también por 'description' (que ahora puede haber cambiado)
    tally_df = tally_df.groupby(["description", columna_colada], as_index=False).agg(agg_dict)
    
    return tally_df

async def process_tally_mtc_cross_reference(
    tally_file: UploadFile, 
    mtc_files: List[UploadFile]
) -> List[Dict[str, Any]]:
    path_tally = None
    files_info_mtc = [] 

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(await tally_file.read())
            path_tally = tmp.name
        
        for f in mtc_files:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(await f.read())
                files_info_mtc.append((tmp.name, f.filename))

        df_resultado = await run_in_threadpool(_proceso_interno, path_tally, files_info_mtc)
        
        if df_resultado.empty:
             return [{"error": "El proceso finalizó pero la tabla resultante está vacía."}]

        return df_resultado.to_dict('records')

    except ValueError as ve:
        return [{"error": str(ve)}]
    except Exception as e:
        return [{"error": f"Error inesperado: {str(e)}"}]
    finally:
        if path_tally and os.path.exists(path_tally):
            try: os.unlink(path_tally)
            except: pass  
        for path_temp, _ in files_info_mtc:
            if path_temp and os.path.exists(path_temp):
                try: os.unlink(path_temp)
                except: pass