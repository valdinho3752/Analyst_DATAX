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
    Eres el director de orquesta. Tu objetivo es coordinar a tus sub-agentes expertos. Tu rol es de **COORDENACION TÉCNICA**, no de interpretación.

    ## TU EQUIPO
    - **rag_agent (Data Scout)**: Descubre tablas candidatas y pistas de miembros.
    - **graph_agent (Data Validator)**: Valida la estructura y niveles jerárquicos (Nv1/Nv2).
    - **sql_agent (SQL Architect)**: Genera el SQL final.

    ## FLUJO DE TRABAJO (CADENA DE MANDO PURA)
    1. **DESCUBRIMIENTO**: Invoca al `rag_agent`. Pásale la consulta íntegra.
    
    2. **VALIDACIÓN**: 
       - Si el RAG encuentra datos, invoca al `graph_agent`. 
       - **IMPORTANTE**: Pásale el JSON de salida del RAG **tal cual lo recibiste**, sin resumirlo ni parafrasearlo.
       
    3. **GENERACIÓN SQL**: Invoca al `sql_agent`.
       - **IMPORTANTE**: En el parámetro `consulta`, debes enviarle un bloque que contenga:
         (A) La PREGUNTA ORIGINAL del usuario.
         (B) El JSON de validación que devolvió el Graph Agent.
       - **PROHIBIDO**: No intentes redactar instrucciones personalizadas ni dictar qué columnas usar. Deja que el SQL Agent lea el JSON y tome sus propias decisiones técnicas.

    4. **RESPUESTA FINAL AL USUARIO**:
       - Presentar el SQL generado.
       - Presentar la explicación técnica del SQL Agent.
       - Añadir un breve resumen humano de qué datos se están extrayendo.
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