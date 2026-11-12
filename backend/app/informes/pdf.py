"""PDF del informe integral (RF-09) con reportlab. Fuente Helvetica (WinAnsi): cubre tildes y ñ."""

import io
from datetime import datetime
from xml.sax.saxutils import escape

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.informes.contrato import AgregadoInforme, SintesisInforme

NIVEL_TEXTO = {
    "inicial": "inicial",
    "basico": "básico",
    "competente": "competente",
    "avanzado": "avanzado",
}


def _nivel(n: str | None) -> str:
    return NIVEL_TEXTO.get(n, n) if n else "sin evidencia"


PIE = "Generado con apoyo de IA; notas calculadas por el sistema y aprobadas por el docente"

_REEMPLAZOS = {
    "—": "-", "–": "-", "‘": "'", "’": "'", "“": '"', "”": '"',
    "•": "-", "→": "->", "…": "...", "≤": "<=", "≥": ">=",
}  # fmt: skip


def _t(texto) -> str:
    """Texto seguro para Paragraph: escapa XML y sustituye lo que Latin-1 no puede dibujar."""
    salida = []
    for c in str(texto):
        c = _REEMPLAZOS.get(c, c)
        try:
            c.encode("cp1252")
        except UnicodeEncodeError:
            c = "?"
        salida.append(c)
    return escape("".join(salida))


def _estilos():
    base = getSampleStyleSheet()
    return {
        "titulo": ParagraphStyle("t", parent=base["Title"], fontSize=24, spaceAfter=18),
        "h1": ParagraphStyle(
            "h1", parent=base["Heading1"], fontSize=15, spaceBefore=14, spaceAfter=8
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading3"], fontSize=11, spaceBefore=8, spaceAfter=3
        ),
        "p": ParagraphStyle("p", parent=base["BodyText"], fontSize=10, leading=14),
        "peq": ParagraphStyle("peq", parent=base["BodyText"], fontSize=8.5, leading=11),
        "centro": ParagraphStyle(
            "c", parent=base["BodyText"], fontSize=12, alignment=1, spaceAfter=6
        ),
    }


def _tabla(filas, anchos, estilo_celda):
    datos = [[Paragraph(_t(c), estilo_celda) for c in fila] for fila in filas]
    tabla = Table(datos, colWidths=anchos, repeatRows=1)
    tabla.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E3E8F0")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#9AA5B8")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return tabla


def _grafico_evolucion(agregado: AgregadoInforme) -> Drawing:
    dibujo = Drawing(16 * cm, 6.5 * cm)
    grafico = VerticalBarChart()
    grafico.x, grafico.y, grafico.width, grafico.height = 40, 35, 16 * cm - 70, 6.5 * cm - 60
    grafico.data = [[lab.nota_final for lab in agregado.laboratorios]]
    grafico.categoryAxis.categoryNames = [lab.codigo for lab in agregado.laboratorios]
    grafico.categoryAxis.labels.fontSize = 7
    grafico.categoryAxis.labels.angle = 30
    grafico.categoryAxis.labels.boxAnchor = "ne"
    grafico.valueAxis.valueMin, grafico.valueAxis.valueMax, grafico.valueAxis.valueStep = 0, 5, 1
    grafico.valueAxis.labels.fontSize = 7
    grafico.bars[0].fillColor = colors.HexColor("#3B6FB6")
    grafico.barLabels.fontSize = 7
    grafico.barLabelFormat = "%.1f"
    grafico.barLabels.nudge = 6
    dibujo.add(grafico)
    dibujo.add(String(40, 6.5 * cm - 14, "Nota final por laboratorio (0,0 - 5,0)", fontSize=8))
    return dibujo


def _pie(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(colors.HexColor("#555555"))
    canvas.drawCentredString(A4[0] / 2, 1.1 * cm, _t_plano(PIE) + f"  |  Página {doc.page}")
    canvas.restoreState()


def _t_plano(texto: str) -> str:
    return "".join(_REEMPLAZOS.get(c, c) for c in texto)


def _fecha(valor: datetime | str) -> str:
    if isinstance(valor, str):
        valor = datetime.fromisoformat(valor)
    return valor.strftime("%d/%m/%Y")


def generar_pdf(
    estudiante_nombre: str,
    generado_en: datetime | str,
    agregado: AgregadoInforme,
    sintesis: SintesisInforme,
    temas_categoria: dict[str, str],
) -> bytes:
    e = _estilos()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title=f"Informe integral - {_t_plano(estudiante_nombre)}",
        author="Asesor Pedagógico Inteligente",
    )
    ancho = A4[0] - 4 * cm
    historia: list = []

    # ---- portada
    historia += [
        Spacer(1, 5 * cm),
        Paragraph("Informe integral de aprendizaje", e["titulo"]),
        Paragraph("Asesor Pedagógico Inteligente", e["centro"]),
        Spacer(1, 1.5 * cm),
        Paragraph(f"<b>Estudiante:</b> {_t(estudiante_nombre)}", e["centro"]),
        Paragraph(f"<b>Fecha:</b> {_fecha(generado_en)}", e["centro"]),
        PageBreak(),
    ]

    # ---- resumen y promedios
    historia.append(Paragraph("Resumen", e["h1"]))
    historia.append(Paragraph(_t(sintesis.resumen), e["p"]))
    historia.append(Spacer(1, 6))
    filas = [
        ["Indicador", "Valor"],
        ["Promedio general", f"{agregado.promedio_general:.2f} ({_nivel(agregado.nivel_general)})"],
    ]
    for cohorte, promedio in agregado.promedio_cohorte.items():
        filas.append([f"Promedio cohorte {cohorte}", f"{promedio:.2f}"])
    if agregado.tendencia is not None:
        filas.append(["Tendencia (cohorte 2 - cohorte 1)", f"{agregado.tendencia:+.2f}"])
    filas.append(
        [
            "Laboratorios evaluados",
            f"{len(agregado.laboratorios)} de {agregado.laboratorios_totales}",
        ]
    )
    historia.append(_tabla(filas, [ancho * 0.55, ancho * 0.45], e["p"]))

    # ---- laboratorios y notas
    historia.append(Paragraph("Laboratorios y notas", e["h1"]))
    filas = [["Código", "Laboratorio", "Cohorte", "Nota"]] + [
        [lab.codigo, lab.titulo, str(lab.cohorte), f"{lab.nota_final:.2f}"]
        for lab in agregado.laboratorios
    ]
    historia.append(_tabla(filas, [ancho * 0.2, ancho * 0.52, ancho * 0.14, ancho * 0.14], e["p"]))

    # ---- competencias
    historia.append(Paragraph("Competencias", e["h1"]))
    if agregado.competencias:
        filas = [["Competencia", "Promedio", "Nivel", "Laboratorios"]] + [
            [c.nombre, f"{c.promedio:.2f}", _nivel(c.nivel_dominio), ", ".join(c.laboratorios)]
            for c in agregado.competencias
        ]
        historia.append(
            _tabla(filas, [ancho * 0.36, ancho * 0.14, ancho * 0.18, ancho * 0.32], e["p"])
        )
    else:
        historia.append(Paragraph("Sin datos de competencias.", e["p"]))

    # ---- evolución
    bloque = [Paragraph("Evolución de las notas", e["h1"])]
    if agregado.laboratorios:
        bloque.append(_grafico_evolucion(agregado))
    historia.append(KeepTogether(bloque))
    historia.append(Paragraph(_t(sintesis.evolucion), e["p"]))

    # ---- temas
    historia.append(Paragraph("Temas, dominio y aprendizajes", e["h1"]))
    for t in agregado.temas:
        nivel = _nivel(t.nivel_dominio)
        promedio = f" ({t.promedio:.2f})" if t.promedio is not None else ""
        categoria = temas_categoria.get(t.tema, "Otros")
        historia.append(
            Paragraph(f"{_t(t.tema)} - {_t(nivel)}{promedio} - {_t(categoria)}", e["h2"])
        )
        for a in t.aprendizajes:
            historia.append(
                Paragraph(
                    f"<b>{_t(a.laboratorio)}</b> ({_t(_nivel(a.nivel_dominio))}): "
                    f"{_t(a.que_aprendio)} "
                    f"Aplicación: {_t(a.como_aplico)}",
                    e["peq"],
                )
            )
        for f in t.que_fortalecer:
            historia.append(Paragraph(f"Por fortalecer: {_t(f)}", e["peq"]))
        if t.laboratorios_sin_evidencia:
            historia.append(
                Paragraph(
                    "Sin evaluación publicada en: " + _t(", ".join(t.laboratorios_sin_evidencia)),
                    e["peq"],
                )
            )

    # ---- brechas
    historia.append(Paragraph("Brechas detectadas", e["h1"]))
    if agregado.brechas:
        filas = [["Tipo", "Nombre", "Detalle"]] + [
            [b.tipo, b.nombre, b.detalle] for b in agregado.brechas
        ]
        historia.append(_tabla(filas, [ancho * 0.18, ancho * 0.3, ancho * 0.52], e["peq"]))
    else:
        historia.append(Paragraph("No se detectaron brechas.", e["p"]))

    # ---- plan
    historia.append(Paragraph("Plan de fortalecimiento", e["h1"]))
    for accion in sorted(sintesis.plan, key=lambda a: a.prioridad):
        historia.append(
            Paragraph(
                f"Prioridad {accion.prioridad}: {_t(accion.tema)} ({accion.plazo_semanas} semanas)",
                e["h2"],
            )
        )
        historia.append(Paragraph(f"<b>Objetivo:</b> {_t(accion.objetivo)}", e["p"]))
        historia.append(
            Paragraph("<b>Actividades:</b> " + _t("; ".join(accion.actividades)), e["p"])
        )
        if accion.recursos:
            historia.append(Paragraph("<b>Recursos:</b> " + _t("; ".join(accion.recursos)), e["p"]))
        historia.append(
            Paragraph(f"<b>Indicador de logro:</b> {_t(accion.indicador_logro)}", e["p"])
        )

    doc.build(historia, onFirstPage=_pie, onLaterPages=_pie)
    return buffer.getvalue()
