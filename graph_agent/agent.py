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
    is_valid: bool
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
        Usa esta tool para CADA tabla. Envía como keywords los valores puros de las `pistas_miembros` y las `keywords_for_graph`.
        
        ## REGLAS DE ORO (MAPEO EXHAUSTIVO)
        1. **Reportar Todos los Niveles**: Tu misión NO es elegir el mejor nivel. Debes listar todos los hallazgos encontrados en Neo4j, indicando claramente a qué nivel pertenecen (Nv1, Nv2, Nv3, Nv4).
        2. **Sin Poda**: Aunque encuentres un Nv2, NO omitas los hallazgos de Nv4. El SQL Agent necesita ver todo el "menú" de opciones para decidir según la pregunta del usuario.
        3. **Fidelidad Léxica**: Asegúrate de que los miembros reportados coincidan exactamente con lo que Neo4j devolvió.
        
        ## FORMATO DE SALIDA (JSON TÉCNICO)
        Sé conciso en `filtered_schema_instructions`. Usa un formato de catálogo:
        - "Encontrado Nv2: [Nombre Miembro] en [Nombre Columna]"
        - "Encontrado Nv4: [Nombre Miembro] en [Nombre Columna]"
        No des consejos de construcción; solo reporta los HECHOS técnicos validados.
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
