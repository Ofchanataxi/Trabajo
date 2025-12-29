import tempfile
import os
import pandas as pd
from fastapi import UploadFile
from typing import List, Dict, Any
from fastapi.concurrency import run_in_threadpool
from app.services.extract_data_from_pdf import extract_data_from_pdf
from app.services.tally_tenaris import config_tally_tenaris 
from app.services.extractors.mtc_extractor import extraer_steel_grade_de_mtc, buscar_coladas_en_pdfs 
from app.services.extractors.pdf_extractor_core import get_adjacent_value

def _proceso_interno(path_tally: str, files_info_mtc: List[tuple], files_info_itp: List[tuple]) -> pd.DataFrame:
    data_raw = extract_data_from_pdf(path_tally, lattice=True)
    if not data_raw:
        raise ValueError("No se pudieron extraer tablas del Tally PDF.")

    tally_df = config_tally_tenaris.obtain_data_tally_tenaris(data_raw)
    
    if not isinstance(tally_df, pd.DataFrame) or tally_df.empty:
        raise ValueError("El procesamiento del Tally no devolvió datos válidos.")

    columna_colada = "Heat #"
    if columna_colada in tally_df.columns:
        tally_df[columna_colada] = tally_df[columna_colada].astype(str).apply(
            lambda x: x.split('-')[0].strip()
        )
    else:
        raise ValueError(f"Columna '{columna_colada}' no encontrada en el Tally.")

    descripcion_material = ""
    for df in data_raw:
        val = get_adjacent_value(df, anchor_text="Material Description", direction="below")
        if val:
            descripcion_material = val
            break

    tally_df["description"] = descripcion_material
    tally_df["quantity"] = 1
    
    coladas_a_buscar = tally_df[columna_colada].unique().tolist()
    
    mapa_resultados_mtc = {}
    if coladas_a_buscar and files_info_mtc:
        mapa_resultados_mtc = extraer_steel_grade_de_mtc(files_info_mtc, coladas_a_buscar)

    mapa_resultados_itp = {}
    if coladas_a_buscar and files_info_itp:
        mapa_resultados_itp = buscar_coladas_en_pdfs(files_info_itp, coladas_a_buscar)

    # --- LÓGICA DE MAPEO DE DATOS ---
    tally_df['Steel Grade'] = tally_df[columna_colada].map(
        lambda x: mapa_resultados_mtc.get(x, {}).get("grade", "No encontrado")
    )

    tally_df['mtcFilename'] = tally_df[columna_colada].map(
        lambda x: mapa_resultados_mtc.get(x, {}).get("file", "-")
    )

    tally_df['itpFilename'] = tally_df[columna_colada].map(
        lambda x: mapa_resultados_itp.get(x, "-")
    )

    def actualizar_descripcion(row):
        colada = str(row[columna_colada])
        info_mtc = mapa_resultados_mtc.get(colada, {})
        tipo_producto = info_mtc.get("product_type", "").upper()
        desc_actual = str(row["description"])

        prefix = ""
        if "TUBING" in tipo_producto:
            prefix = "Tubing"
        elif "CASING" in tipo_producto:
            prefix = "Casing"
        
        if prefix and not desc_actual.upper().startswith(prefix):
            return prefix + desc_actual
        
        return desc_actual

    if mapa_resultados_mtc:
        tally_df['description'] = tally_df.apply(actualizar_descripcion, axis=1)

    agg_dict = {
        "quantity": "sum",
        "Steel Grade": "first",
        "mtcFilename": "first",
        "itpFilename": "first"
    }
    
    if "Length" in tally_df.columns:
        agg_dict["Length"] = "sum"

    tally_df = tally_df.groupby(["description", columna_colada], as_index=False).agg(agg_dict)

    tally_df = tally_df.rename(columns={
        columna_colada: "heat",
        "Steel Grade": "steelGrade"
    })

    tally_df["condition"] = "NUEVO"
    
    return tally_df

async def process_tally_mtc_cross_reference(
    tally_file: UploadFile, 
    mtc_files: List[UploadFile],
    itp_files: List[UploadFile] = [] # Nuevo parámetro
) -> List[Dict[str, Any]]:
    path_tally = None
    files_info_mtc = [] 
    files_info_itp = []

    try:
        # Guardar Tally temporal
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(await tally_file.read())
            path_tally = tmp.name
        
        # Guardar MTCs temporales
        for f in mtc_files:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(await f.read())
                files_info_mtc.append((tmp.name, f.filename))

        # Guardar ITPs temporales (NUEVO)
        for f in itp_files:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(await f.read())
                files_info_itp.append((tmp.name, f.filename))

        # Pasamos files_info_itp a la función interna
        df_resultado = await run_in_threadpool(_proceso_interno, path_tally, files_info_mtc, files_info_itp)
        
        if df_resultado.empty:
             return [{"error": "El proceso finalizó pero la tabla resultante está vacía."}]

        return df_resultado.to_dict('records')

    except ValueError as ve:
        return [{"error": str(ve)}]
    except Exception as e:
        return [{"error": f"Error inesperado: {str(e)}"}]
    finally:
        # Limpieza de archivos temporales
        if path_tally and os.path.exists(path_tally):
            try: os.unlink(path_tally)
            except: pass  
        for path_temp, _ in files_info_mtc:
            if path_temp and os.path.exists(path_temp):
                try: os.unlink(path_temp)
                except: pass
        for path_temp, _ in files_info_itp: # Limpieza ITP
            if path_temp and os.path.exists(path_temp):
                try: os.unlink(path_temp)
                except: pass