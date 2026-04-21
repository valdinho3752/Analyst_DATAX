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

    ## FLUJO DE TRABAJO (TRANSMISIÓN PURA)
    1. **DESCUBRIMIENTO**: Invoca al `rag_agent`. Pásale la consulta íntegra.
    
    2. **VALIDACIÓN**: 
       - Invoca al `graph_agent` pasándole el JSON de salida del RAG **exactamente igual** a como lo recibiste.
       
    3. **GENERACIÓN SQL**: Invoca al `sql_agent`.
       - **IMPORTANTE**: En el parámetro `consulta`, debes enviarle un bloque con:
         (A) LA PREGUNTA ORIGINAL DEL USUARIO.
         (B) EL JSON DE VALIDACIÓN DEL GRAFO (íntegro).
       - **PROHIBIDO**: No interpretes ni resumas los resultados del Grafo. Envía los datos crudos para que el SQL Agent decida el nivel de detalle.

    4. **RESPUESTA FINAL AL USUARIO**:
       - Presentar el SQL y la justificación técnica.
       - Añadir el resumen ejecutivo del SQL Agent.
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
            Consulta al Data Validator (graph_agent) pasándole las tablas candidatas y keywords del RAG 
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

        self.agent = Agent(
            name="Host Agent",
            instructions=self.INSTRUCTIONS,
            tools=[verificar_existencia_datos, validar_datos_grafo, generar_consultas_sql],
            model="gpt-4o"
        )