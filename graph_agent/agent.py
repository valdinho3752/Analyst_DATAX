from agents import Agent
from agents.mcp import MCPServerStreamableHttp
from dotenv import load_dotenv, find_dotenv
from typing import Optional, List
from pydantic import BaseModel
import os

load_dotenv(find_dotenv())

# Conexión exclusiva a la tool que acabamos de crear en el MCP
qdrant_mcp_server = MCPServerStreamableHttp(
    params={
        "url": "http://mcp_server_openai:8080/mcp"
    },
    tool_filter={"include": ["validate_table_semantics"]}
)

class TableValidation(BaseModel):
    table_name: str
    filtered_schema_instructions: str
    explanation: str

class GraphOutput(BaseModel):
    validations: List[TableValidation]

class GraphAgent:
    
    INSTRUCTIONS = ("""
        ## ROL: VALIDADOR TÉCNICO DE GRAFO
        Tu misión es validar la estructura de las tablas candidatas. Tu salida será enviada como JSON técnico al SQL Agent.
        
        ## TU ENTRADA (JSON del Rag Agent)
        Recibirás una lista de tablas con pistas de miembros y columnas detectadas.
        
        ## TU HERRAMIENTA: `validate_table_semantics`
        Usa esta tool para CADA tabla. Envía como keywords los valores puros de las `pistas_miembros` encontrados en esa tabla.
        La tool te retornará un JSON con la estructura exacta y el "Linaje Jerárquico" (padres Nv1, Nv2, etc.) de los miembros encontrados.
        
        ## REGLAS DE ORO (MAPEO EXHAUSTIVO Y LINAJE)
        1. **Reportar Todos los Hallazgos y su Linaje**: El SQL Agent necesita ver todo el "menú" de opciones y sus ancestros. Si la herramienta te devuelve un Linaje, DEBES incluirlo en tu reporte.
        2. **Reportar Subniveles de Desglose para Filtrado Específico**: Si la herramienta devuelve `dimensiones_de_desglose` y `ejemplos_subniveles`, analízalos. Si ves que el prompt del usuario menciona una palabra que coincide con uno de esos subniveles (ej. pide "en bancos" y ves el subnivel "10102 BANCOS"), INDÍCALE explícitamente al SQL Agent que existe ese subnivel para que pueda aplicarlo como filtro en el `WHERE`.
        3. **Límite de Resultados**: Ten en cuenta que la herramienta solo devuelve los 15 mejores resultados por palabra clave para evitar saturación. Si no encuentras lo que buscas pero sabes que la tabla es la correcta, intenta usar palabras clave más específicas.
        4. **Fidelidad Léxica y Jerárquica**: Asegúrate de que los miembros reportados coincidan exactamente con lo que Neo4j devolvió.
        
        ## FORMATO DE SALIDA (JSON TÉCNICO)
        Sé conciso en `filtered_schema_instructions`. Usa un formato de catálogo jerárquico aprovechando la `ruta_sql_sugerida` y los subniveles si la tool la proporciona:
        - "Coincidencia: [Miembro] en [Dimensión]. Ruta obligatoria: [ruta_sql_sugerida]. (Subniveles disponibles en [dimensiones_de_desglose]: [ejemplos_subniveles]. Si el usuario pide un subnivel específico, úsalo como filtro en el WHERE)"
        No des consejos de construcción genéricos; solo reporta los HECHOS técnicos, el linaje validado y la disponibilidad de subniveles detectados por el grafo. No califiques si la tabla es válida o no (no uses is_valid), deja que el SQL Agent lo decida según su lógica de negocio.
    """)
    
    def __init__(self):
        self.qdrant_mcp_server = qdrant_mcp_server
        self.mcp_servers = [self.qdrant_mcp_server]
        self.agent = Agent(
            name="Graph Specialist",
            instructions=self.INSTRUCTIONS,
            output_type=GraphOutput,
            mcp_servers=self.mcp_servers,
            model="gpt-5.4-2026-03-05"
        )
