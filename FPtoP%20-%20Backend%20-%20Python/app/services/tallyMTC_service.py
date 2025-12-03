import tempfile
import os
import pandas as pd
from fastapi import UploadFile
from typing import List, Dict, Any
from fastapi.concurrency import run_in_threadpool
from app.services.extract_data_from_pdf import extract_data_from_pdf
from app.services.tally_tenaris import config_tally_tenaris 
from app.services.extractors.mtc_extractor import extraer_steel_grade_de_mtc

def _proceso_interno(path_tally: str, paths_mtc: List[str]) -> pd.DataFrame:
    """
    Lógica síncrona pesada: Procesa el Tally y busca en los MTCs.
    """
    data_raw = extract_data_from_pdf(path_tally, lattice=True)
    if not data_raw:
        raise ValueError("No se pudieron extraer tablas del Tally PDF.")

    tally_df = config_tally_tenaris.obtain_data_tally_tenaris(data_raw)
    
    if not isinstance(tally_df, pd.DataFrame) or tally_df.empty:
        raise ValueError("El procesamiento del Tally no devolvió datos válidos.")
    
    columna_colada = "Heat #"
    if columna_colada not in tally_df.columns:
        raise ValueError(f"Columna '{columna_colada}' no encontrada en el Tally. Disponibles: {tally_df.columns.tolist()}")

    coladas_a_buscar = tally_df[columna_colada].astype(str).unique().tolist()
    
    if not coladas_a_buscar:
        return tally_df 

    mapa_grades = extraer_steel_grade_de_mtc(paths_mtc, coladas_a_buscar)
    
    tally_df['Steel Grade'] = tally_df[columna_colada].astype(str).map(mapa_grades)
    
    return tally_df

async def process_tally_mtc_cross_reference(
    tally_file: UploadFile, 
    mtc_files: List[UploadFile]
) -> List[Dict[str, Any]]:
    """
    Orquestador principal. Maneja archivos temporales y ejecución en hilo aparte.
    """
    path_tally = None
    paths_mtc = []

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(await tally_file.read())
            path_tally = tmp.name
        
        for f in mtc_files:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(await f.read())
                paths_mtc.append(tmp.name)

        df_resultado = await run_in_threadpool(_proceso_interno, path_tally, paths_mtc)
        
        if df_resultado.empty:
             return {"error": "El proceso finalizó pero la tabla resultante está vacía."}

        return df_resultado.to_dict('records')

    except ValueError as ve:
        return {"error": str(ve)}
        
    except Exception as e:
        return {"error": f"Error inesperado: {str(e)}"}
    
    finally:
        if path_tally and os.path.exists(path_tally):
            try: os.unlink(path_tally)
            except: pass
            
        for p in paths_mtc:
            if p and os.path.exists(p):
                try: os.unlink(p)
                except: pass