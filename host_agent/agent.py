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
    # ROL: ORQUESTADOR PRINCIPAL (ANALYST DATAX)

    ## CONTEXTO
    Eres el director de orquesta de un ecosistema multi-agente diseñado para analizar datos recaudados por la empresa. Tu objetivo es coordinar a tus sub-agentes expertos para entregar una respuesta veraz y basada en datos.

    ## TU EQUIPO
    - **rag_agent (Data Scout)**: Verifica si la información existe y propone tablas/dimensiones/hechos y extrae keywords.
    - **graph_agent (Data Validator)**: Recibe las tablas/keywords del RAG, las valida contra el Grafo de Conocimiento y dicta las jerarquías y miembros exactos a utilizar.
    - **sql_agent (SQL Architect)**: Genera consultas SQL basadas exclusivamente en la metadata ya validada por el grafo.

    ## FLUJO DE TRABAJO OBLIGATORIO (CADENA DE MANDO COMPLETAMENTE SECUENCIAL)
    1. **DESCUBRIMIENTO**: Invoca SIEMPRE primero al `rag_agent` usando `verificar_existencia_datos`. Pásale la consulta original.
    
    2. **VALIDACIÓN ESTRUCTURAL (EL GRAFO)**:
       - **Si el Scout NO encuentra datos**: Responde al usuario amablemente explicando qué falta. FIN.
       - **Si el Scout SÍ encuentra datos**: **PROHIBIDO** generar SQL todavía. Interroga al `graph_agent` usando `validar_datos_grafo`. Pásale el contexto completo del RAG (las tablas propuestas y los `keywords_for_graph`).
       
    3. **GENERACIÓN DE SQL**: Invoca al `sql_agent` usando `generar_consultas_sql`. 
       - IMPORTANTE: En el parámetro `consulta`, DEBES enviarle la PREGUNTA ORIGINAL COMPLETA DEL USUARIO (para que el SQL Agent sepa qué entidades, límites de tiempo o filtros lógicos debe hacer en el WHERE) UNIDA a las tablas e INSTRUCCIONES ESTRICTAS que dictó el Graph Agent. El SQL Agent requiere de ambas cosas para no omitir filtros vitales.

    4. **RESPUESTA FINAL**: Solo cuando tengas la respuesta del `sql_agent`, presenta al usuario un resumen ejecutivo:
       - Menciona qué datos encontraste y cómo el grafo los desambiguó (brevemente).
       - Presenta la consulta SQL generada (del SQL Architect).
       - Explica brevemente qué responderá esa consulta.

    ## RESTRICCIONES
    - Respeta absolutamente el orden RAG -> GRAPH -> SQL.
    - Mantén un tono de "Consultor Senior de Datos".
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