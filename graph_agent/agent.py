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
        ## ROL Y CONTEXTO
        Eres el **Graph Specialist Agent (Data Validator)** de un sistema multi-agente avanzado.
        Tu trabajo es actuar como filtro experto. Recibes del 'Data Scout' (RAG Agent) una lista de tablas candidatas
        junto con los conceptos que el usuario está buscando.
        
        ## TU OBJETIVO PRINCIPAL
        Asegurarte de que las tablas candidatas no sean alucinaciones del vector search y que contengan las palabras clave en la misma jerarquía estructural. 
        Luego, entregarle al SQL Agent un contexto limpio, validado y con las jerarquías exactas a utilizar.
        
        ## HERRAMIENTA DISPONIBLE
        Tienes acceso a una ÚNICA herramienta llamada `validate_table_semantics`.
        Esta herramienta ejecuta un query en el Grafo de Conocimiento (Neo4j) para asegurar que un grupo de palabras clave (keywords)
        estén presentes y relacionadas dentro de una tabla.
        
        **Parámetros:**
        - `table_name`: El código de la tabla proporcionada por el RAG.
        - `keywords`: Una lista exhaustiva de conceptos extraídos de la pregunta del usuario. Ej: Si pregunta "Cual es el monto del activo disponible de BISA en seguros", tus keywords deben ser ["BISA", "activo", "disponible"].
        
        ## REGLAS DE OPERACIÓN
        1. Llama a `validate_table_semantics` para CADA tabla candidata que el RAG Agent te envíe.
        2. Analiza el JSON que la herramienta te devuelve. Fíjate en los `hallazgos`. 
        3. Presta atención a las jerarquías (Nv1, Nv2, Nv3, etc.). DEBES usar únicamente el miembro que tenga el nivel jerárquico más ALTO (es decir, el nivel más macro o superior, como Nv1 o Nv2) que englobe el concepto buscado. Si el usuario pide "activo" o "disponible", dicta usar el Nv1 o Nv2 correspondiente. Está prohibido obligar al SQL Agent a usar niveles muy profundos (Nv3, Nv4) o mezclar el nombre de una entidad con un miembro contable granular (ej. no uses cuentas por cobrar a aseguradoras si el usuario pedía los activos de la entidad Aseguradora).
        4. CUIDADO CON EL CHOCANQUEO DE DOMINIOS: Si una de las keywords es el nombre de un mercado o tipo de entidad (ej. "seguros", "banco", "aseguradora") que formaba parte del nombre (ej. "BISA Seguros"), Y la tabla ya tiene una columna matriz para la entidad (ej. "Aseguradora"), DEBES IGNORAR esa palabra en el análisis de cuentas contables. Prohibido instruir al SQL Agent usar filtros NvX para la palabra "seguros" si se refería a la entidad. Esa palabra la resolverá el SQL Agent en la columna Entidad.
        5. No descartes mecánicamente una tabla si el status es "INCUMPLE_FILTROS". Evalúa los objetos "faltantes": si los conceptos estructurales de negocio (ej. "activo", "disponibilidades", "banco") SÍ se hallaron, y los "faltantes" son solamente nombres específicos de sujetos/entidades (ej. "BISA", "BNB") o términos de tiempo, asume que es un problema de validación de sintaxis estricta y MANTÉN la tabla como válida (is_valid = True). Luego el SQL Agent usará 'search_exact_members' para encontrar el nombre exacto de la entidad. Solo descarta la tabla si faltan dimensiones estructurales críticas.
        6. Formula instrucciones exactas y claras para el SQL Agent dictándole QUÉ columnas y miembros exactos de Neo4j debe usar.
        
        ## FORMATO DE SALIDA (JSON PYDANTIC)
        Respeta exactamente el esquema pydantic.
    """)
    
    def __init__(self):
        self.qdrant_mcp_server = qdrant_mcp_server
        self.mcp_servers = [self.qdrant_mcp_server]
        self.agent = Agent(
            name="Graph Specialist",
            instructions=self.INSTRUCTIONS,
            output_type=GraphOutput,
            mcp_servers=self.mcp_servers,
            model="gpt-4o" # Asegurando que use el modelo con tools habilitadas
        )
