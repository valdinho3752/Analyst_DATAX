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
        
        ## REGLAS DE ORO (PODA JERÁRQUICA)
        1. **Dictar el Nivel Más Alto**: Si el usuario pregunta por un concepto macro (ej. "Activo", "Disponible"), y el Grafo confirma que existe un Nv1 o Nv2 que los contiene, DEBES dictar únicamente el uso de ese Nv1/Nv2.
        2. **PROHIBICIÓN ESTRICTA**: Está terminantemente prohibido listar cuentas granulares (Nv3, Nv4, Nv5) en el campo `filtered_schema_instructions` si el nivel Nv1 o Nv2 es suficiente para cubrir la consulta. No ensucies el input del SQL Agent con listas de cuentas detalladas a menos que el usuario haya pedido un detalle específico.
        3. **Tratamiento de Faltantes**: Si el status es `INCUMPLE_FILTROS` pero los conceptos estructurales de negocio (ej. "Activo", "Banco") sí están, marca `is_valid=True` y explica que la estructura es correcta pese a faltar nombres comerciales específicos (como "BISA").
        
        ## FORMATO DE SALIDA (JSON TÉCNICO)
        Sé extremadamente breve en `filtered_schema_instructions`. Usa el formato: "Usar Columna X con Miembro Y en Nv2".
        No des discursos ni consejos de negocio; solo hechos estructurales validados.
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
