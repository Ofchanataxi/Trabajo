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
    
    # Iteramos sobre las tablas crudas para encontrar el encabezado global
    for df in data_raw:
        # Buscamos el valor DEBAJO de "Material Description"
        val = get_adjacent_value(df, anchor_text="Material Description", direction="below")
        if val:
            descripcion_material = val
            break

    # Llenar todos con la misma descripcion encontrada
    tally_df["description"] = descripcion_material
    
    # Inicializamos cantidad en 1 para que al sumar (agrupar) nos de el conteo de tubos
    tally_df["quantity"] = 1
    
    columna_colada = "Heat #"
    if columna_colada not in tally_df.columns:
        raise ValueError(f"Columna '{columna_colada}' no encontrada en el Tally. Disponibles: {tally_df.columns.tolist()}")

    coladas_a_buscar = tally_df[columna_colada].astype(str).unique().tolist()
    
    # Si no hay coladas, retornamos, pero igual aplicamos agrupación por consistencia
    if coladas_a_buscar:
        # Llamamos al extractor pasando la lista de tuplas (path, filename)
        mapa_resultados = extraer_steel_grade_de_mtc(files_info_mtc, coladas_a_buscar)
        
        # Mapeamos los resultados: Grado
        tally_df['Steel Grade'] = tally_df[columna_colada].astype(str).map(
            lambda x: mapa_resultados.get(x, {}).get("grade", "No encontrado")
        )

        # Mapeamos los resultados: Archivo origen
        tally_df['mtcFilename'] = tally_df[columna_colada].astype(str).map(
            lambda x: mapa_resultados.get(x, {}).get("file", "-")
        )
    else:
        tally_df['Steel Grade'] = ""
        tally_df['mtcFilename'] = ""
    
    agg_dict = {
        "quantity": "sum",
        "Steel Grade": "first",
        "mtcFilename": "first"
    }

    # Realizamos la agrupación
    tally_df = tally_df.groupby(["description", columna_colada], as_index=False).agg(agg_dict)
    
    return tally_df

async def process_tally_mtc_cross_reference(
    tally_file: UploadFile, 
    mtc_files: List[UploadFile]
) -> List[Dict[str, Any]]:

    path_tally = None
    files_info_mtc = [] # Inicializamos la lista correcta

    try:
        # Guardar Tally temporal
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(await tally_file.read())
            path_tally = tmp.name
        
        # Guardar MTCs temporales y registrar sus nombres originales
        for f in mtc_files:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(await f.read())
                # Guardamos la tupla (ruta_temporal, nombre_original)
                files_info_mtc.append((tmp.name, f.filename))

        # Ejecutar proceso pesado en hilo
        df_resultado = await run_in_threadpool(_proceso_interno, path_tally, files_info_mtc)
        
        if df_resultado.empty:
             return [{"error": "El proceso finalizó pero la tabla resultante está vacía."}]

        return df_resultado.to_dict('records')

    except ValueError as ve:
        return [{"error": str(ve)}]
        
    except Exception as e:
        return [{"error": f"Error inesperado: {str(e)}"}]
    
    finally:
        # Bloque de limpieza único al final
        if path_tally and os.path.exists(path_tally):
            try: os.unlink(path_tally)
            except: pass
            
        for path_temp, _ in files_info_mtc:
            if path_temp and os.path.exists(path_temp):
                try: os.unlink(path_temp)
                except: pass