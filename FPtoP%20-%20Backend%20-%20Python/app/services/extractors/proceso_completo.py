import pandas as pd
from typing import List, Dict, Any

# --- Reutilizamos tus funciones existentes ---
# 1. Tu extractor de tablas de PDF
from app.services.extract_data_from_pdf import extract_data_from_pdf 
# 2. Tu lógica de negocio de Tenaris (asumimos que existe desde)
from app.services.tally_tenaris import config_tally_tenaris 
# 3. Nuestro nuevo extractor de MTC
from app.services.extractors.mtc_extractor import extraer_steel_grade_de_mtc

def obtener_datos_tally_procesados(path_tally_pdf: str) -> pd.DataFrame:
    """
    Esta función simula la extracción y procesamiento del Tally de Tenaris,
    reutilizando tu lógica existente.
    """
    print(f"Procesando Tally Tenaris: {path_tally_pdf}")
    # 1. Reutilizar la extracción de tablas
    data_raw = extract_data_from_pdf(path_tally_pdf, lattice=True) 
    
    if data_raw is None or len(data_raw) == 0:
        print("Error: No se extrajeron tablas del Tally PDF.")
        return pd.DataFrame() # Devolver DataFrame vacío

    # 2. Reutilizar la lógica de negocio de Tenaris
    # Esta función (obtain_data_tally_tenaris) es tuya.
    # Asumimos que devuelve una LISTA DE DICCIONARIOS
    lista_de_datos: List[Dict[str, Any]] = config_tally_tenaris.obtain_data_tally_tenaris(data_raw)
    
    if not lista_de_datos:
        print("Error: config_tally_tenaris no devolvió datos.")
        return pd.DataFrame()

    # Convertir a DataFrame de Pandas (ya que está en tu requirements.txt)
    # para facilitar la manipulación
    tally_df = pd.DataFrame(lista_de_datos)
    
    # --- IMPORTANTE: Asegúrate que el nombre de la columna sea correcto ---
    # Si tu función `config_tally_tenaris` devuelve un nombre diferente 
    # para la colada (ej: 'Colada', 'HEAT'), ajusta esto.
    if "Heat N°" not in tally_df.columns:
        print("Error: La columna 'Heat N°' no se encontró en los datos del Tally.")
        print(f"Columnas disponibles: {tally_df.columns.tolist()}")
        return pd.DataFrame()
        
    print(f"Tally procesado. Se encontraron {len(tally_df)} items.")
    return tally_df

def proceso_completo_tally_mtc(path_tally_pdf: str, path_mtc_pdf: str) -> pd.DataFrame:
    """
    Función de orquestación principal.
    """
    
    # 1. Obtener datos del Tally (reutilizando tu lógica)
    tally_df = obtener_datos_tally_procesados(path_tally_pdf)
    
    if tally_df.empty:
        print("Proceso detenido. No hay datos del Tally.")
        return pd.DataFrame()

    # 2. Obtener la lista única de coladas a buscar
    # Usamos .astype(str) por si acaso hay números y texto
    coladas_a_buscar = tally_df["Heat N°"].astype(str).unique().tolist()
    
    if not coladas_a_buscar:
        print("No se encontraron 'Heat N°' para buscar en el MTC.")
        return tally_df # Devolver el Tally original
        
    # 3. Extraer Steel Grades del MTC para esa lista de coladas
    mapa_colada_a_grade = extraer_steel_grade_de_mtc(path_mtc_pdf, coladas_a_buscar)
    
    # 4. Combinar los resultados en una nueva columna
    # .map() de Pandas es la forma más eficiente de hacer esto
    tally_df['Steel Grade (del MTC)'] = tally_df['Heat N°'].astype(str).map(mapa_colada_a_grade)
    
    return tally_df

# --- Ejemplo de cómo ejecutarlo ---
if __name__ == "__main__":
    # --- Cambia estas rutas por tus archivos reales ---
    PATH_TALLY = "ruta/a/tu/tally_tenaris.pdf"
    PATH_MTC = "ruta/a/tu/MTC.pdf"
    
    print("--- Iniciando proceso de cruce Tally vs MTC ---")
    
    # Aquí faltaría tu lógica para obtener los archivos
    # (por ejemplo, desde un endpoint de FastAPI)
    
    # Simulamos que los archivos existen en esas rutas
    try:
        resultados_df = proceso_completo_tally_mtc(PATH_TALLY, PATH_MTC)
        
        if not resultados_df.empty:
            print("\n--- Resultados Finales ---")
            # .to_string() imprime el DataFrame completo en la consola
            print(resultados_df.to_string())
            
            # Opcional: Guardar en un Excel/CSV
            # resultados_df.to_excel("resultados_combinados.xlsx", index=False)
            
    except FileNotFoundError:
        print("\nError: Asegúrate de que las rutas a los archivos PDF son correctas.")
    except Exception as e:
        print(f"\nHa ocurrido un error inesperado: {e}")