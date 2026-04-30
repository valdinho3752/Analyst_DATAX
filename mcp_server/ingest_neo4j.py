import json
import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

# Cargar variables de entorno del .env de la raíz
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# Configuración Neo4j default (ahora apuntando al nombre del contenedor)
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "testpassword")

INPUT_FILE = "metadata/chunks_demo4.json"

class GraphIngestor:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def create_constraints(self):
        """Crear índices para inserciones rápidas y sin duplicados"""
        with self.driver.session() as session:
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (t:Table) REQUIRE t.name IS UNIQUE")
            session.run("CREATE INDEX IF NOT EXISTS FOR (d:Dimension) ON (d.name, d.table)")
            session.run("CREATE INDEX IF NOT EXISTS FOR (m:Member) ON (m.name, m.dimension, m.table)")
            print("✅ Índices y constraints creados.")

    def ingest_table(self, payload):
        """Ingesta el nodo de la tabla madre."""
        query_table = """
        MERGE (t:Table {name: $name})
        SET t.dataset = $dataset,
            t.description = $desc,
            t.source = $source,
            t.granularity = $granularity,
            t.theme = $theme,
            t.language = $language
        """
        
        with self.driver.session() as session:
            session.run(query_table, 
                        name=payload.get("nombre_tabla"),
                        dataset=payload.get("Nombre dataset"),
                        desc=payload.get("Descripcion tabla"),
                        source=payload.get("Fuente"),
                        granularity=payload.get("Granularidad"),
                        theme=payload.get("Tematica"),
                        language=payload.get("Idioma"))

    def ingest_dimension(self, payload):
        """Ingesta el nodo Dimensión y lo vincula a la Tabla."""
        query = """
        MATCH (t:Table {name: $table})
        MERGE (d:Dimension {name: $name, table: $table})
        SET d.datatype = $datatype,
            d.dimtype = $dimtype,
            d.hierarchy = $hierarchy,
            d.description = $desc
        MERGE (d)-[:BELONGS_TO]->(t)
        """
        with self.driver.session() as session:
            session.run(query,
                        table=payload.get("tabla_origen"),
                        name=payload.get("nombre_columna"),
                        datatype=payload.get("Tipo dato"),
                        dimtype=payload.get("Tipo dimension"),
                        hierarchy=payload.get("Jerarquia"),
                        desc=payload.get("Descripcion"))

    def ingest_fact(self, payload):
        """Ingesta el nodo de un hecho y lo vincula a la Tabla."""
        query = """
        MATCH (t:Table {name: $table})
        MERGE (f:Fact {name: $name, table: $table})
        SET f.datatype = $datatype,
            f.facttype = $facttype,
            f.unit = $unit,
            f.aggregation = $aggregation,
            f.forbidden_aggs = $forbidden,
            f.description = $desc,
            f.dependencies = $depend
        MERGE (f)-[:MEASURES]->(t)
        """
        with self.driver.session() as session:
            session.run(query,
                        table=payload.get("tabla_origen"),
                        name=payload.get("nombre_columna"),
                        datatype=payload.get("Tipo dato"),
                        facttype=payload.get("Tipo hecho"),
                        unit=payload.get("Unidad de medida"),
                        aggregation=payload.get("Funcioenes de agregacion"),
                        forbidden=payload.get("Funciones de agregacion prohibidas"),
                        desc=payload.get("Descripcion"),
                        depend=payload.get("Dependencias"))

    def ingest_member(self, payload):
        """Ingesta el nodo Miembro literal y lo vincula a su Dimensión específica."""
        query = """
        MATCH (d:Dimension {name: $dimension, table: $table})
        MERGE (m:Member {name: $value, dimension: $dimension, table: $table})
        MERGE (m)-[:BELONGS_TO]->(d)
        """
        with self.driver.session() as session:
            session.run(query,
                        table=payload.get("tabla_origen"),
                        dimension=payload.get("nombre_columna"),
                        value=str(payload.get("valor_miembro")))

    def link_dimensions_hierarchy(self):
        """Conecta dimensiones Nv(X) a Nv(X-1) dentro de la misma tabla."""
        query_get = """
        MATCH (d:Dimension)-[:BELONGS_TO]->(t:Table)
        WHERE d.name =~ '(?i).*Nv[0-9]+.*'
        RETURN t.name AS table, d.name AS dim_name
        """
        import re
        links_to_create = []
        with self.driver.session() as session:
            records = session.run(query_get)
            table_dims = {}
            for r in records:
                t = r["table"]
                d = r["dim_name"]
                match = re.search(r'(?i)Nv(\d+)', d)
                if match:
                    level = int(match.group(1))
                    if t not in table_dims:
                        table_dims[t] = []
                    table_dims[t].append((level, d))
            
            for t, dims in table_dims.items():
                dims.sort(key=lambda x: x[0])
                for i in range(1, len(dims)):
                    child_dim = dims[i][1]
                    parent_dim = dims[i-1][1]
                    links_to_create.append((t, child_dim, parent_dim))
        
        query_merge = """
        MATCH (child:Dimension {name: $child, table: $table})
        MATCH (parent:Dimension {name: $parent, table: $table})
        MERGE (child)-[:CHILD_OF]->(parent)
        """
        with self.driver.session() as session:
            for link in links_to_create:
                session.run(query_merge, table=link[0], child=link[1], parent=link[2])
        print(f"✅ Se crearon {len(links_to_create)} relaciones CHILD_OF entre Dimensiones.")

    def link_members_hierarchy(self):
        """Conecta miembros de niveles inferiores a superiores comparando prefijos numéricos."""
        query = """
        MATCH (childDim:Dimension)-[:CHILD_OF]->(parentDim:Dimension)
        MATCH (childMember:Member)-[:BELONGS_TO]->(childDim)
        MATCH (parentMember:Member)-[:BELONGS_TO]->(parentDim)
        WHERE childMember.table = parentMember.table
          AND childMember.name <> parentMember.name
        WITH childMember, parentMember, split(parentMember.name, ' ')[0] AS parentCode
        WHERE childMember.name STARTS WITH parentCode
        WITH childMember, parentMember, size(parentCode) as prefLen
        ORDER BY prefLen DESC
        WITH childMember, collect(parentMember)[0] as bestParent
        MERGE (childMember)-[:CHILD_OF]->(bestParent)
        """
        with self.driver.session() as session:
            result = session.run(query)
            counters = result.consume().counters
            print(f"✅ Se crearon {counters.relationships_created} relaciones CHILD_OF entre Miembros.")


def main():
    input_path = os.path.abspath(os.path.join(os.path.dirname(__file__), INPUT_FILE))
    print(f"📖 Leyendo archivo para Grafo: {input_path}...")
    
    try:
        with open(input_path, "r", encoding="utf-8") as f:
            chunks = json.load(f)
    except Exception as e:
        print(f"❌ Error al leer archivo: {e}")
        return

    ingestor = GraphIngestor(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    ingestor.create_constraints()
    
    print(f"🚀 Procesando {len(chunks)} chunks hacia Neo4j...")
    
    # 1. Ingestar Tablas primero (puntos de anclaje)
    for c in chunks:
        p = c.get("payload", {})
        if p.get("tipo") == "tabla_maestra":
            ingestor.ingest_table(p)
            
    # 2. Ingestar Dimensiones
    for c in chunks:
        p = c.get("payload", {})
        if p.get("tipo") == "dimension":
            ingestor.ingest_dimension(p)
            
    # 3. Ingestar Hechos
    for c in chunks:
        p = c.get("payload", {})
        if p.get("tipo") == "hecho":
            ingestor.ingest_fact(p)
            
    # 4. Ingestar Miembros (se anclan a las Dimensiones)
    for c in chunks:
        p = c.get("payload", {})
        if p.get("tipo") == "miembro_dimension":
            ingestor.ingest_member(p)
            
    # 5. Generar Jerarquías Post-Ingesta
    print("🔗 Generando relaciones jerárquicas (CHILD_OF)...")
    ingestor.link_dimensions_hierarchy()
    ingestor.link_members_hierarchy()
            
    print("✅ Ingesta en el Grafo finalizada exitosamente.")
    ingestor.close()

if __name__ == "__main__":
    main()
