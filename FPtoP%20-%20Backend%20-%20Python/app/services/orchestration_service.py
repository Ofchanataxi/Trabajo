import tempfile
import os
import pandas as pd
from fastapi import UploadFile
from typing import List, Dict, Any

# Reutilizamos tus funciones existentes
from app.services.extract_data_from_pdf import extract_data_from_pdf
from app.services.tally_tenaris import config_tally_tenaris 

# Importamos nuestro nuevo extractor de MTC
from app.services.extractors.mtc_extractor import extraer_steel_grade_de_mtc

# --- FUNCIÓN MODIFICADA ---
def _obtener_datos_tally_procesados(path_tally_pdf: str) -> pd.DataFrame:
    """
    Función interna para procesar el Tally PDF.
    Ahora lanza 'ValueError' con errores específicos.
    """
    print(f"Procesando Tally Tenaris: {path_tally_pdf}")
    
    # 1. Reutilizar la extracción de tablas
    data_raw = extract_data_from_pdf(path_tally_pdf, lattice=True) 
    
    if data_raw is None or len(data_raw) == 0:
        # --- CAMBIO 1: Lanzar un error específico ---
        raise ValueError("No se extrajeron tablas del Tally PDF.") 

    # 2. Reutilizar la lógica de negocio de Tenaris
    tally_df = config_tally_tenaris.obtain_data_tally_tenaris(data_raw)
    
    if not isinstance(tally_df, pd.DataFrame):
        # --- CAMBIO 2: Lanzar un error específico ---
        raise ValueError(f"Error de tipo: config_tally_tenaris no devolvió un DataFrame. Devolvió: {type(tally_df)}")

    if tally_df.empty: 
        # --- CAMBIO 3: Lanzar un error específico ---
        raise ValueError("config_tally_tenaris devolvió un DataFrame vacío (no se procesaron datos).")

    # --- IMPORTANTE: Revisa este nombre de columna ---
    columna_colada = "Heat #" 

    if columna_colada not in tally_df.columns:
        # --- CAMBIO 4: Lanzar un error específico y útil ---
        error_msg = f"La columna '{columna_colada}' no se encontró en los datos del Tally. Columnas disponibles: {tally_df.columns.tolist()}"
        print(error_msg)
        raise ValueError(error_msg)
        
    print(f"Tally procesado. Se encontraron {len(tally_df)} items.")
    return tally_df

def _proceso_completo_tally_mtc(path_tally_pdf: str, path_mtc_pdf: str) -> pd.DataFrame:
    """
    Función de orquestación principal (sin cambios, propagará el error)
    """
    # 1. Obtener datos del Tally (esta función ahora puede lanzar un ValueError)
    tally_df = _obtener_datos_tally_procesados(path_tally_pdf)
    
    # 2. Obtener la lista única de coladas a buscar
    coladas_a_buscar = tally_df["Heat #"].astype(str).unique().tolist()
    
    if not coladas_a_buscar:
        # Esto es improbable si el cheque anterior pasó, pero es buena práctica
        raise ValueError("No se encontraron 'Heat #' para buscar en el MTC.")
        
    # 3. Extraer Steel Grades del MTC
    mapa_colada_a_grade = extraer_steel_grade_de_mtc(path_mtc_pdf, coladas_a_buscar)
    
    # 4. Combinar los resultados en una nueva columna
    tally_df['Steel Grade (del MTC)'] = tally_df['Heat #'].astype(str).map(mapa_colada_a_grade)
    
    return tally_df

# --- FUNCIÓN MODIFICADA ---
async def process_tally_mtc_cross_reference(
    tally_file: UploadFile, 
    mtc_file: UploadFile
) -> List[Dict[str, Any]]:
    """
    Esta es la función que la API llamará.
    Ahora captura los 'ValueError' y los devuelve como el error de la API.
    """
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_tally:
        tmp_tally.write(await tally_file.read())
        path_tally = tmp_tally.name
        
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_mtc:
        tmp_mtc.write(await mtc_file.read())
        path_mtc = tmp_mtc.name

    try:
        # Llamar a la función de lógica principal
        resultados_df = _proceso_completo_tally_mtc(path_tally, path_mtc)
        
        # --- CAMBIO 5: Este cheque ahora es más específico ---
        if resultados_df.empty:
            # Esto puede ocurrir si _obtener_datos_tally_procesados tuvo éxito
            # pero _proceso_completo_tally_mtc devolvió vacío (aunque ahora es menos probable)
            return {"error": "El Tally fue procesado, pero el resultado final está vacío (quizás no hubo cruces)."}
        
        # Convertir el DataFrame a un formato JSON (lista de diccionarios)
        return resultados_df.to_dict('records')

    # --- CAMBIO 6: Capturar los errores específicos que definimos ---
    except ValueError as ve:
        print(f"Error de negocio en process_tally_mtc_cross_reference: {ve}")
        # Devolvemos el mensaje de error específico
        return {"error": str(ve)} 
    
    except Exception as e:
        print(f"Error inesperado en process_tally_mtc_cross_reference: {e}")
        return {"error": f"Error inesperado: {str(e)}"}
    
    finally:
        # Asegurarse de borrar los archivos temporales
        os.unlink(path_tally)
        os.unlink(path_mtc)