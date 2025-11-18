import tempfile
import os
import pandas as pd
from fastapi import UploadFile
from typing import List, Dict, Any
from app.services.extract_data_from_pdf import extract_data_from_pdf
from app.services.tally_tenaris import config_tally_tenaris 
from app.services.extractors.mtc_extractor import extraer_steel_grade_de_mtc

def _obtener_datos_tally_procesados(path_tally_pdf: str) -> pd.DataFrame:

    print(f"Procesando Tally Tenaris: {path_tally_pdf}")
    
    data_raw = extract_data_from_pdf(path_tally_pdf, lattice=True) 
    
    if data_raw is None or len(data_raw) == 0:
        raise ValueError("No se extrajeron tablas del Tally PDF.") 

    tally_df = config_tally_tenaris.obtain_data_tally_tenaris(data_raw)
    
    if not isinstance(tally_df, pd.DataFrame):
        raise ValueError(f"Error de tipo: config_tally_tenaris no devolvió un DataFrame. Devolvió: {type(tally_df)}")

    if tally_df.empty: 
        raise ValueError("config_tally_tenaris devolvió un DataFrame vacío (no se procesaron datos).")

    columna_colada = "Heat #" 

    if columna_colada not in tally_df.columns:
        error_msg = f"La columna '{columna_colada}' no se encontró en los datos del Tally. Columnas disponibles: {tally_df.columns.tolist()}"
        print(error_msg)
        raise ValueError(error_msg)
        
    print(f"Tally procesado. Se encontraron {len(tally_df)} items.")
    return tally_df

def _proceso_completo_tally_mtc(path_tally_pdf: str, path_mtc_pdf: str) -> pd.DataFrame:
    tally_df = _obtener_datos_tally_procesados(path_tally_pdf)
    
    coladas_a_buscar = tally_df["Heat #"].astype(str).unique().tolist()
    
    if not coladas_a_buscar:

        raise ValueError("No se encontraron 'Heat #' para buscar en el MTC.")

    mapa_colada_a_grade = extraer_steel_grade_de_mtc(path_mtc_pdf, coladas_a_buscar)
    
    tally_df['Steel Grade'] = tally_df['Heat #'].astype(str).map(mapa_colada_a_grade)
    
    return tally_df

async def process_tally_mtc_cross_reference(
    tally_file: UploadFile, 
    mtc_file: UploadFile
) -> List[Dict[str, Any]]:

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_tally:
        tmp_tally.write(await tally_file.read())
        path_tally = tmp_tally.name
        
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_mtc:
        tmp_mtc.write(await mtc_file.read())
        path_mtc = tmp_mtc.name

    try:
        resultados_df = _proceso_completo_tally_mtc(path_tally, path_mtc)
        
        if resultados_df.empty:
            return {"error": "El Tally fue procesado, pero el resultado final está vacío (quizás no hubo cruces)."}
        
        return resultados_df.to_dict('records')

    except ValueError as ve:
        print(f"Error de negocio en process_tally_mtc_cross_reference: {ve}")
        return {"error": str(ve)} 
    
    except Exception as e:
        print(f"Error inesperado en process_tally_mtc_cross_reference: {e}")
        return {"error": f"Error inesperado: {str(e)}"}
    
    finally:
        os.unlink(path_tally)
        os.unlink(path_mtc)