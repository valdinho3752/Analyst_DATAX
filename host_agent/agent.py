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
    - **rag_agent (Data Scout)**: Verifica si la información existe y en qué tablas/dimensiones/hechos.
    - **sql_agent (SQL Architect)**: Genera consultas SQL basadas en la metadata encontrada.

    ## FLUJO DE TRABAJO OBLIGATORIO (CADENA DE MANDO)
    1. **DESCUBRIMIENTO**: Invoca SIEMPRE primero al `rag_agent` usando `verificar_existencia_datos`. Pásale la consulta original.
    
    2. **DECISIÓN TÉCNICA**:
       - **Si el Scout NO encuentra datos**: Responde al usuario amablemente explicando qué falta. FIN.
       - **Si el Scout SÍ encuentra datos**: **PROHIBIDO** responder al usuario todavía. Debes proceder al paso 3 inmediatamente.

    3. **GENERACIÓN DE SQL**: Invoca al `sql_agent` usando `generar_consultas_sql`. 
       - IMPORTANTE: En el parámetro `consulta`, incluye tanto la pregunta del usuario como el resumen de tablas/columnas que te dio el Scout para darle contexto total al Arquitecto SQL.

    4. **RESPUESTA FINAL**: Solo cuando tengas la respuesta del `sql_agent`, presenta al usuario un resumen ejecutivo:
       - Menciona qué datos encontraste (del Scout).
       - Presenta la consulta SQL generada (del SQL Architect).
       - Explica brevemente qué responderá esa consulta.

    ## RESTRICCIONES
    - NUNCA des una respuesta final sin intentar generar el SQL si los datos existen.
    - Mantén un tono de "Consultor Senior de Datos".
    """


    def __init__(self):
        # Configuración de la conexión al sub-agente RAG
        rag_url = os.getenv("RAG_AGENT_URL", "http://localhost:10000")
        self.rag_connection = RemoteAgentConnection(rag_url)
        sql_url = os.getenv("SQL_AGENT_URL", "http://localhost:10001")
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
        async def generar_consultas_sql(consulta: str) -> str:
            """
            Consulta al SqlAgent para generar consultas SQL para obtener datos de la base de datos.
            
            Args:
                consulta: La pregunta original del usuario o el tema a investigar.
            """
            try:
                result = await self.sql_connection.send_message(consulta)
                return str(result)
            except Exception as e:
                return f"Error al contactar al sql_agent: {str(e)}"

        self.agent = Agent(
            name="Host Agent",
            instructions=self.INSTRUCTIONS,
            tools=[verificar_existencia_datos],
            model="gpt-4o"
        )