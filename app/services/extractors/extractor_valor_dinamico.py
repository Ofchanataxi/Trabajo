import pandas as pd
from typing import Dict, Optional, List
from app.services.extract_data_from_pdf import extract_data_from_pdf
from app.services.extractors.pdf_extractor_core import get_adjacent_value

def _buscar_en_tablas(
    tablas: Optional[List[pd.DataFrame]], 
    valor_a_buscar: str, 
    posicion_dato: str, 
    modo_busqueda: str # "stream" o "lattice"
) -> Optional[Dict[str, str]]:
    if not tablas:
        return None
        
    for i, df in enumerate(tablas):
        valor_encontrado = get_adjacent_value(
            df, 
            anchor_text=valor_a_buscar, 
            direction=posicion_dato
        )
        if valor_encontrado is not None:
            print(f"  Encontrado en Tabla {modo_busqueda} {i}: {valor_encontrado}")
            return {
                "valor_buscado": valor_a_buscar,
                "posicion": posicion_dato,
                "valor_encontrado": valor_encontrado,
                "modo_busqueda": modo_busqueda
            }
    return None # No encontrado en esta lista de tablas


def extraer_valor_dinamico(
    pdf_path: str, 
    valor_a_buscar: Optional[str], 
    posicion_dato: Optional[str],
    modo_busqueda: Optional[str]
) -> Optional[Dict[str, str]]:
    """
    Extractor dinámico (ID 333) que busca un valor adyacente.
    - Si posicion_dato == 'inline', prioriza lattice=False (stream).
    - Para otras posiciones, prioriza lattice=True (grid).
    """
    print(f"--- Ejecutando extractor_valor_dinamico (ID 333) ---")
    print(f"Buscando: '{valor_a_buscar}', Posición: '{posicion_dato}'")
    
    if not valor_a_buscar or not posicion_dato:
        return {"error": "Para release_type 333, 'valor_a_buscar' y 'posicion_dato' son requeridos."}

    if modo_busqueda == "lattice":
        # 1. Prioridad: Lattice (lattice=True)
        print("Paso 1: Buscando adyacente en modo 'lattice' (lattice=True)...")
        lattice_tables = extract_data_from_pdf(pdf_path, lattice=True)
        resultado = _buscar_en_tablas(lattice_tables, valor_a_buscar, posicion_dato, "lattice")
        if resultado:
            return resultado
        
    else:
        # 1. Prioridad: Stream (lattice=False)
        print("Paso 1: Buscando 'inline' en modo 'stream' (lattice=False)...")
        stream_tables = extract_data_from_pdf(pdf_path, lattice=False)
        resultado = _buscar_en_tablas(stream_tables, valor_a_buscar, posicion_dato, "stream")
        if resultado:
            return resultado

    # --- FIN ---
    print("No se encontró el valor en ningún modo.")
    return None