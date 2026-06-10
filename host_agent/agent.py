import os
from agents import Agent, function_tool
from dotenv import load_dotenv, find_dotenv
from typing import Optional, List
from remote_connection import RemoteAgentConnection

load_dotenv(find_dotenv())

class HostAgent:
    """
    Agente Orquestador Principal. 
    Su misión es recibir consultas de negocio y coordinar a los agentes expertos.
    """
    
    INSTRUCTIONS = """
    # ROL: COORDINADOR TRANSPARENTE (ANALYST DATAX)

    ## CONTEXTO
    Eres el coordinador técnico del flujo. Tu misión es asegurar que los agentes expertos reciban la metadata técnica original sin alteraciones.

    ## TU EQUIPO
    - **rag_agent**: Descubrimiento de tablas y miembros.
    - **graph_agent**: Validación de hechos y mapeo jerárquico multinivel (Nv1-Nv4).
    - **sql_agent**: Arquitecto SQL que decide la profundidad basándose en el prompt original.
    - **sql_executor_agent**: Experto en ejecución que corre el SQL en Postgres y devuelve los datos.
    - **pdf_agent**: Experto en diseño y compilación de reportes elegantes en PDF usando LaTeX.

    ## FLUJO DE TRABAJO (TRANSMISIÓN PURA)
    1. **DESCUBRIMIENTO**: Invoca al `rag_agent`. Pásale la consulta íntegra.
    
    2. **VALIDACIÓN**: 
       - Invoca al `graph_agent` pasándole el JSON de salida del RAG **exactamente igual** a como lo recibiste.
       
    3. **GENERACIÓN SQL**: Invoca al `sql_agent`.
       - **IMPORTANTE**: En el parámetro `consulta`, debes enviarle un bloque con:
         (A) LA PREGUNTA ORIGINAL DEL USUARIO.
         (B) EL JSON DE VALIDACIÓN DEL GRAFO (íntegro).
       - **PROHIBIDO**: No interpretes ni resumas los resultados del Grafo. Envía los datos crudos para que el SQL Agent decida el nivel de detalle.

    4. **EJECUCIÓN Y AUTO-CORRECCIÓN**:
       - Toma el bloque de código SQL generado por el `sql_agent` e invoca al `sql_executor_agent`.
       - **IMPORTANTE**: Pásale el JSON ÍNTEGRO que recibiste del `sql_agent`.
       - **BUCLE DE RETROALIMENTACIÓN (Máximo 2 veces)**: Si el `sql_executor_agent` devuelve una tabla vacía, un mensaje de "sin resultados" o un error de sintaxis, DEBES volver al paso 3 e invocar nuevamente al `sql_agent`.
       - **LÍMITE**: Si después de 2 intentos de corrección el resultado sigue siendo vacío, detén el proceso y responde al usuario que no se encontraron datos para los criterios solicitados.
       - Al re-invocar al `sql_agent`, explícale qué falló (ej: "La consulta no devolvió datos") y envíale de nuevo el contexto completo para que ajuste los filtros (posiblemente subiendo de nivel de jerarquía Nv3 -> Nv2).

    5. **GENERACIÓN DE PDF**:
       - Invoca SIEMPRE la herramienta `generar_reporte_pdf` una vez que obtengas los resultados del `sql_executor_agent`. Pásale un bloque con la pregunta original, la justificación, la consulta SQL utilizada y los resultados finales obtenidos. Esto asegura que el usuario siempre tenga un reporte en PDF elegante disponible para descargar.

    6. **RESPUESTA FINAL AL USUARIO**:
       - **Consulta Generada**: Incluye siempre el bloque de código SQL íntegro que el `sql_agent` diseñó.
       - **Justificación**: Añade la explicación técnica de por qué se eligieron esas tablas y filtros.
       - **Resultados Ejecutados**: Muestra la tabla de datos (o el mensaje de éxito) que devolvió el `sql_executor_agent`.
       - **Reporte PDF**: Incluye siempre el enlace markdown devuelto por la herramienta `generar_reporte_pdf` (ej: `[Descargar Reporte PDF](/reports/report_XYZ.pdf)`) para que el usuario pueda descargarlo.
       - **Transparencia**: El usuario debe ver tanto la lógica técnica (SQL) como la respuesta de negocio (Datos) y el reporte en PDF.
    """


    def __init__(self):
        # Configuración de la conexión al sub-agente RAG
        rag_url = os.getenv("RAG_AGENT_URL", "http://rag_agent_openai:10000")
        self.rag_connection = RemoteAgentConnection(rag_url)
        
        # Conexión al Graph Agent (Nuevo)
        graph_url = os.getenv("GRAPH_AGENT_URL", "http://graph_agent_openai:10003")
        self.graph_connection = RemoteAgentConnection(graph_url)
        
        sql_url = os.getenv("SQL_AGENT_URL", "http://sql_agent_openai:10001")
        self.sql_connection = RemoteAgentConnection(sql_url)

        # Conexión al SQL Executor Agent (Nuevo)
        executor_url = os.getenv("SQL_EXECUTOR_URL", "http://sql_executor_agent_openai:10004")
        self.executor_connection = RemoteAgentConnection(executor_url)
        
        # Conexión al PDF Agent (Nuevo)
        pdf_url = os.getenv("PDF_AGENT_URL", "http://pdf_agent_openai:10005")
        self.pdf_connection = RemoteAgentConnection(pdf_url)
        
        @function_tool
        async def verificar_existencia_datos(consulta: str) -> str:
            """
            Consulta al Data Scout (rag_agent) para verificar si los datos solicitados existen en la base de datos.
            
            Args:
                consulta: La pregunta original del usuario o el tema a investigar.
            """
            try:
                result = await self.rag_connection.send_message(consulta)
                return str(result)
            except Exception as e:
                return f"Error al contactar al rag_agent: {str(e)}"

        @function_tool
        async def validar_datos_grafo(contexto_rag: str) -> str:
            """
            Consulta al Data Validator (graph_agent) pasándole las tablas candidatas del RAG 
            para verificar la jerarquía exacta y descartar alucinaciones usando el Knowledge Graph.
            """
            try:
                result = await self.graph_connection.send_message(contexto_rag)
                return str(result)
            except Exception as e:
                return f"Error al contactar al graph_agent: {str(e)}"

        @function_tool
        async def generar_consultas_sql(consulta: str) -> str:
            """
            Consulta al SqlAgent para generar consultas SQL usando la metadata estructural provista.
            """
            try:
                result = await self.sql_connection.send_message(consulta)
                return str(result)
            except Exception as e:
                return f"Error al contactar al sql_agent: {str(e)}"

        @function_tool
        async def ejecutar_sql_en_db(sql: str) -> str:
            """
            Consulta al SqlExecutorAgent para ejecutar una consulta SQL y obtener los resultados de la base de datos.
            """
            try:
                result = await self.executor_connection.send_message(sql)
                return str(result)
            except Exception as e:
                return f"Error al contactar al sql_executor_agent: {str(e)}"

        @function_tool
        async def generar_reporte_pdf(contexto_reporte: str) -> str:
            """
            Consulta al PDF Agent pasándole el contexto del reporte para que diseñe y compile el documento PDF.
            
            Args:
                contexto_reporte: Un bloque de texto estructurado que incluya la pregunta original del usuario, la justificación, la consulta SQL ejecutada y los datos resultantes obtenidos de la base de datos.
            """
            try:
                result = await self.pdf_connection.send_message(contexto_reporte)
                return str(result)
            except Exception as e:
                return f"Error al contactar al pdf_agent: {str(e)}"

        self.agent = Agent(
            name="Host Agent",
            instructions=self.INSTRUCTIONS,
            tools=[
                verificar_existencia_datos, 
                validar_datos_grafo, 
                generar_consultas_sql, 
                ejecutar_sql_en_db, 
                generar_reporte_pdf
            ],
            model="gpt-4o"
        )