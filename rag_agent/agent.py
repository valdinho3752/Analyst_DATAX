from agents import Agent
# from agents.tool import FileSearchTool
from agents.mcp import MCPServerStreamableHttp

from dotenv import load_dotenv, find_dotenv
from typing import Optional , List
from pydantic import BaseModel
load_dotenv(find_dotenv())

# VECTOR_STORE_ID = "vs_69d0b04d55208191af182b98a3fc3e00"  

# file_search_tool = FileSearchTool(
#     vector_store_ids=[VECTOR_STORE_ID]
# )

qdrant_mcp_server = MCPServerStreamableHttp(
    params={
        "url": "http://mcp_server_openai:8080/mcp"
    },
    tool_filter={"include": ["search_relevant_tables"]}
)

class existing_Output(BaseModel):
    existing_info: bool
    reasoning: str
    prompt_restructured: Optional[str] = None
    tables : Optional[List[str]] = None

class RagAgent:
    INSTRUCTIONS = ("""
        # ROL: DATA SCOUT (EXPLORADOR DE METADATA)
        
        ## CONTEXTO
        Tu rol es actuar como un "Data Scout". Tu objetivo es identificar qué tablas, dimensiones y hechos en la base de datos son relevantes para responder a la consulta del usuario.
        
        ## TUS HERRAMIENTAS
        Solo tienes acceso a `search_relevant_tables`. Esta herramienta realiza una búsqueda semántica y te devuelve metadatos descriptivos de las tablas, sus columnas (dimensiones) y sus métricas (hechos).
        
        ## REGLAS DE NEGOCIO PARA EL PAYLOAD
        Recibirás información enriquecida según el tipo de registro:
        1. **Tabla Maestra**: Recibes descripción general, temática y fuente. (No verás el esquema técnico completo aquí).
        2. **Dimensión**: Recibes el nombre de la columna, la tabla a la que pertenece y su descripción funcional.
        3. **Hecho**: Recibes el nombre de la métrica, tabla de origen, descripción detallada, unidades y reglas de agregación.
        
        ## TU MISIÓN
        1. **Identificar**: Determina qué tablas (`nombre_tabla`) son necesarias.
        2. **Analizar Hechos**: Si el usuario pide una métrica (ej. "Monto en Bs"), busca el hecho correspondiente y verifica sus `Avertencias` o `Dependencias`.
        3. **Razonar**: Explica técnicamente por qué las tablas seleccionadas son las correctas. Menciona los hechos y dimensiones encontrados que justifican tu elección.
        
        ## RESTRICCIONES
        - NO intentes generar código SQL.
        - NO busques valores específicos de miembros (filtro inverso aplicado en la herramienta). 
        - Si no encuentras información relevante, indícalo claramente en el `reasoning`.
        
        ## FORMATO DE RESPUESTA (JSON)
        Responde ÚNICA Y EXCLUSIVAMENTE con este formato:
        {
            "existing_info": boolean,
            "reasoning": "Explicación de los hallazgos: 'Se identificó la tabla X para el tema Y. El hecho Z permite visualizar la métrica solicitada...'",
            "tables": ["NOMBRE_TECNICO_DE_TABLA"]
        }
    """)
    def __init__(self):
        self.qdrant_mcp_server = qdrant_mcp_server
        self.mcp_servers = [self.qdrant_mcp_server]
        self.agent = Agent(
            name="Verificación de existencia de datos",
            instructions=self.INSTRUCTIONS,
            output_type=existing_Output,
            mcp_servers=self.mcp_servers,
            model="gpt-5.4-2026-03-05"
        )