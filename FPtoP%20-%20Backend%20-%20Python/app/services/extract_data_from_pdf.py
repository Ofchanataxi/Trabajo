import tabula
import pandas as pd
from pathlib import Path
from pypdf import PdfReader, PdfWriter

def createExcel(tables):
    if not tables:
        print("No se detectaron tablas en el PDF.")
    else:
        output_path = "tablas_detectadas.xlsx"
        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            for i, df in enumerate(tables, start=1):
                sheet_name = f"Tabla_{i}"
                df.to_excel(writer, index=False, sheet_name=sheet_name)
                print(f"✅ Guardada {sheet_name} con {len(df)} filas")

    print(f"\n📁 Archivo Excel generado: {output_path}")
    return None



def obtainDataFromTables(pdf_path: str, lattice: bool=True, pages: str="all"):
    dataframe = []
    try:
        tables = tabula.read_pdf(str(pdf_path), pages=pages, multiple_tables=True, lattice=lattice, pandas_options={'dtype': str})

        print(tables)
        print("tables tipo")
        print(type(tables))
        dataframe = tables
        if(lattice):
            createExcel(tables)
        #print(tables)
    except Exception as e:
        print(f"Error al leer el PDF con Tabula: {e}")
        return dataframe
    return dataframe


def normalize_rotation(input_pdf: str | Path) -> Path:
    input_pdf = Path(input_pdf)
    output_pdf = input_pdf.with_name(input_pdf.stem + "_rot0.pdf")

    reader = PdfReader(str(input_pdf))
    writer = PdfWriter()

    for page in reader.pages:
        # pypdf expone .rotation; si no, lee el /Rotate
        rot = getattr(page, "rotation", None)
        if rot is None:
            rot = (page.get("/Rotate") or 0) % 360
        else:
            rot = rot % 360

        if rot:
            try:
                # pypdf moderno: rotación antihoraria positiva
                page.rotate(-rot)
            except AttributeError:
                # compatibilidad con variantes
                if rot == 90:
                    _try_rotate_legacy(page, ccw=90)
                elif rot == 180:
                    _try_rotate_legacy(page, cw=180)  # 180 es simétrica
                elif rot == 270:
                    _try_rotate_legacy(page, cw=90)
        writer.add_page(page)

    with open(output_pdf, "wb") as f:
        writer.write(f)
    return output_pdf

def _try_rotate_legacy(page, cw: int | None = None, ccw: int | None = None):
    """Compatibilidad con PyPDF2 viejas y nombres snake/camel."""
    if ccw is not None:
        for name in ("rotateCounterClockwise", "rotate_counter_clockwise"):
            meth = getattr(page, name, None)
            if meth:
                meth(ccw)
                return
    if cw is not None:
        for name in ("rotateClockwise", "rotate_clockwise"):
            meth = getattr(page, name, None)
            if meth:
                meth(cw)
                return
    raise AttributeError("No rotate method available on this PageObject")

def extract_data_from_pdf(pdf_path: str, lattice: bool=True, pages: str="all") -> dict:
    print(f"extract_data (lattice={lattice})")

    fixed_pdf = normalize_rotation(pdf_path)

    dataFromTables = obtainDataFromTables(fixed_pdf, lattice, pages=pages)
    if len(dataFromTables) == 0:
        return None

    print("Si encontre datos voy a continuar")

    return dataFromTables