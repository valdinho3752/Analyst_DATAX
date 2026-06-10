import os
import subprocess
import tempfile
import uuid
import shutil
from agents import Agent, function_tool
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

class PdfAgent:
    
    INSTRUCTIONS = """
    ## ROL: DISEÑADOR Y COMPILADOR DE REPORTES LATEX CON GRÁFICOS
    Tu misión es diseñar reportes en PDF elegantes y formales a partir de la información de negocio y los resultados estructurados (tablas). Debes ser capaz de tomar decisiones inteligentes sobre la inclusión de gráficos explicativos.
    
    ## DECISIÓN Y GENERACIÓN DE GRÁFICOS (AESTHETICS WOW)
    1. **Analiza los Datos y la Consulta**:
       - Si los datos representan una **serie de tiempo** o evolución a través de gestiones/años/meses: Genera un gráfico de líneas (`line chart`) para ilustrar la tendencia temporal.
       - Si los datos **comparan múltiples categorías, entidades o conceptos** (por ejemplo, saldo disponible en diferentes compañías de seguros): Genera un gráfico de barras (`bar chart`) o barras horizontales para facilitar la visualización comparativa.
       - Si representas la **distribución porcentual** o participación de partes sobre un total: Genera un gráfico de torta (`pie chart`) o barras apiladas.
       - Si es una respuesta puntual con una única celda de datos: No generes gráfico, mantén el diseño limpio con texto y tabla.
    2. **Escribe el Código de Python**:
       - Crea un código Python limpio y autocontenido.
       - **OBLIGATORIO**: Guarda siempre el gráfico final como `'grafico.png'` usando `plt.savefig('grafico.png', dpi=300, bbox_inches='tight')`.
       - Limpia y cierra la figura usando `plt.close()`.
       - Usa estilos profesionales en el gráfico:
         - Colores corporativos (ej: azul marino `#1E3A8A`, turquesa `#0D9488`, gris pizarra `#475569`, verde bosque `#10B981`).
         - Agrega títulos (`plt.title`), etiquetas de ejes (`plt.xlabel`, `plt.ylabel`) y leyenda si hay múltiples series.
         - Usa fondos limpios (por ejemplo, cuadrículas muy tenues con `plt.grid(True, linestyle='--', alpha=0.5)`).
    3. **Inserta el Gráfico en LaTeX**:
       - Asegúrate de incluir los paquetes `graphicx` (`\\usepackage{graphicx}`) y `float` (`\\usepackage{float}`) en tu preámbulo de LaTeX.
       - Inserta el gráfico en el cuerpo del reporte usando:
         `\\begin{figure}[H]`
         `\\centering`
         `\\includegraphics[width=0.85\\textwidth]{grafico.png}`
         `\\caption{Representación gráfica de los datos analizados.}`
         `\\end{figure}`

    ## REGLAS DE DISEÑO LATEX (AESTHETICS WOW)
    1. **Estructura limpia**: Usa la clase `article` con márgenes profesionales: `\\usepackage[margin=2.5cm]{geometry}`.
    2. **Tipografía moderna**: Usa fuentes profesionales (por ejemplo, Helvetica: `\\usepackage{helvet}` y `\\renewcommand{\\familydefault}{\\sfdefault}`).
    3. **Colores corporativos**: Define colores agradables usando `xcolor` (por ejemplo, azul oscuro para secciones, gris pizarra para texto secundario):
       `\\definecolor{primary}{HTML}{1E3A8A}`
       `\\definecolor{secondary}{HTML}{475569}`
    4. **Secciones estilizadas**: Usa `titlesec` para dar color a los títulos de las secciones.
    5. **Tablas Premium**:
       - Usa el paquete `booktabs` (`\\toprule`, `\\midrule`, `\\bottomrule`).
       - Evita líneas verticales en las tablas.
       - Centra las tablas con `\\begin{table}[H]` o `\\begin{table}[h]` e incluye `\\centering`.
       - Asegúrate de incluir el paquete `float` si usas `[H]`.
    6. **Idioma**: Usa `\\usepackage[spanish]{babel}` para el formato de fechas y palabras clave en español.
    7. **Especial cuidado con caracteres especiales**: Escapa caracteres como `%`, `_`, `&`, `#` en LaTeX (usa `\\%`, `\\_`, `\\&`, `\\#`). Si hay nombres de columnas, celdas o explicaciones con estos caracteres, ¡escápalos obligatoriamente!

    ## TU FLUJO
    1. Analiza los resultados y decide si conviene incluir un gráfico y de qué tipo.
    2. Diseña el código Python necesario para generar y guardar el gráfico como `'grafico.png'`.
    3. Diseña el código LaTeX completo que contenga:
       - Título formal (ej. "Reporte de Análisis de Datos - Analyst DATAX").
       - Resumen ejecutivo/justificación del análisis.
       - La consulta SQL utilizada (en un bloque de código formateado, ej. `\\begin{verbatim}`).
       - Una tabla bien estructurada con los resultados en formato LaTeX.
       - El gráfico (si aplica) referenciado mediante `\\includegraphics{grafico.png}`.
       - Conclusiones o notas del análisis.
    4. Invoca la herramienta `compilar_pdf` pasándole el código LaTeX y el código Python del gráfico (opcional).
    5. Retorna la respuesta con la URL del PDF que te devuelve la herramienta de forma clara (formato markdown: `[Descargar Reporte PDF](/reports/report_XYZ.pdf)`).
    """

    def __init__(self):
        
        @function_tool
        def compilar_pdf(codigo_latex: str, codigo_python_grafico: str = None) -> str:
            """
            Compila código LaTeX en un PDF, permitiendo generar un gráfico en Python previamente.
            
            Args:
                codigo_latex: El código LaTeX completo a compilar.
                codigo_python_grafico: Opcional. Código Python autocontenido que genera un gráfico y lo guarda como 'grafico.png'.
            Returns:
                La URL relativa al reporte PDF generado para que el cliente lo descargue.
            """
            reports_dir = "/app/reports"
            os.makedirs(reports_dir, exist_ok=True)
            
            # Generar un nombre único para el reporte
            report_id = uuid.uuid4().hex[:8]
            pdf_filename = f"reporte_{report_id}.pdf"
            
            # Crear directorio temporal para la compilación
            with tempfile.TemporaryDirectory() as tmpdir:
                # 1. Generar gráfico si se provee el script de python
                if codigo_python_grafico:
                    py_path = os.path.join(tmpdir, "generate_chart.py")
                    with open(py_path, "w", encoding="utf-8") as pf:
                        pf.write(codigo_python_grafico)
                    try:
                        subprocess.run(
                            ["python", "generate_chart.py"],
                            cwd=tmpdir,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            check=True
                        )
                    except subprocess.CalledProcessError as e:
                        py_error = f"Error al ejecutar código de gráfico de Python:\n{e.stderr.decode('utf-8', errors='ignore')}"
                        return py_error

                # 2. Escribir el documento LaTeX
                tex_path = os.path.join(tmpdir, "document.tex")
                with open(tex_path, "w", encoding="utf-8") as f:
                    f.write(codigo_latex)
                
                # Ejecutar pdflatex
                try:
                    # Primera pasada para referencias
                    subprocess.run(
                        ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "document.tex"],
                        cwd=tmpdir,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        check=True
                    )
                    # Segunda pasada para tablas y referencias cruzadas
                    subprocess.run(
                        ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "document.tex"],
                        cwd=tmpdir,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        check=True
                    )
                except subprocess.CalledProcessError as e:
                    # En caso de error, leer el log de pdflatex para ayudar al agente a auto-corregirse
                    log_path = os.path.join(tmpdir, "document.log")
                    error_msg = f"Error de compilación LaTeX:\n{e.stderr.decode('utf-8', errors='ignore')}"
                    if os.path.exists(log_path):
                        with open(log_path, "r", encoding="utf-8", errors="ignore") as lf:
                            log_content = lf.read()
                        # Devolver las últimas 40 líneas del log
                        log_lines = log_content.splitlines()[-40:]
                        error_msg += "\n\nFragmento del LOG de pdflatex:\n" + "\n".join(log_lines)
                    return error_msg
                
                # Mover el archivo PDF al volumen de reportes compartidos
                output_pdf = os.path.join(tmpdir, "document.pdf")
                dest_pdf = os.path.join(reports_dir, pdf_filename)
                
                if os.path.exists(output_pdf):
                    shutil.copy(output_pdf, dest_pdf)
                    # Retornar la URL relativa del reporte
                    return f"/reports/{pdf_filename}"
                else:
                    return "Error: No se generó el PDF de salida."

        self.agent = Agent(
            name="PDF Compiler Agent",
            instructions=self.INSTRUCTIONS,
            tools=[compilar_pdf],
            model="gpt-4o"
        )
