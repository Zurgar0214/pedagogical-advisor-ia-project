"""Generadores de archivos de prueba (PDF, ZIP, PNG) sin dependencias extra."""

import io
import zipfile


def pdf_bytes(lineas: list[str] | None = None) -> bytes:
    """PDF mínimo válido de una página; con `lineas` None/vacío no tiene texto."""
    lineas = lineas or []
    flujo = "BT /F1 12 Tf 50 750 Td 14 TL " + " ".join(f"({t}) Tj T*" for t in lineas) + " ET"
    flujo_b = flujo.encode("latin-1") if lineas else b""
    objetos = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(flujo_b)).encode() + b" >>\nstream\n" + flujo_b + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    salida = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, cuerpo in enumerate(objetos, start=1):
        offsets.append(len(salida))
        salida += f"{i} 0 obj\n".encode() + cuerpo + b"\nendobj\n"
    inicio_xref = len(salida)
    salida += f"xref\n0 {len(objetos) + 1}\n".encode() + b"0000000000 65535 f \n"
    for off in offsets:
        salida += f"{off:010d} 00000 n \n".encode()
    salida += (
        f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\nstartxref\n{inicio_xref}\n%%EOF\n"
    ).encode()
    return bytes(salida)


LINEAS_INFORME = [f"Linea numero {i} del informe de laboratorio con contenido suficiente" for i in range(8)]


def pdf_con_texto() -> bytes:
    return pdf_bytes(LINEAS_INFORME)


def pdf_sin_texto() -> bytes:
    return pdf_bytes([])


def zip_bytes(entradas: dict[str, bytes] | None = None) -> bytes:
    entradas = entradas or {"main.py": b"print('hola')\n", "README.md": b"# Proyecto\n"}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        for nombre, datos in entradas.items():
            z.writestr(nombre, datos)
    return buffer.getvalue()


PNG_CABECERA = b"\x89PNG\r\n\x1a\n"


def png_bytes(relleno: int = 100) -> bytes:
    return PNG_CABECERA + b"\x00" * relleno
