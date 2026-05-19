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

INPUT_FILE = "metadata/chunks_demo8.json"

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
        WHERE d.name CONTAINS "Nv" OR d.name CONTAINS "nv"
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

        // 1. Extraemos el prefijo inicial (código)
        WITH childMember, parentMember, 
             split(parentMember.name, ' ')[0] AS rawParentCode,
             split(childMember.name, ' ')[0] AS rawChildCode

        // 2. Limpieza Nivel 1: Reemplazamos la extensión decimal de relleno '.00' si existe
        WITH childMember, parentMember,
             (CASE WHEN rawParentCode ENDS WITH ".00" THEN substring(rawParentCode, 0, size(rawParentCode)-3) ELSE rawParentCode END) AS p1,
             (CASE WHEN rawChildCode ENDS WITH ".00" THEN substring(rawChildCode, 0, size(rawChildCode)-3) ELSE rawChildCode END) AS c1

        // 3. Limpieza Nivel 2: Quitamos el primer cero a la derecha (si lo tiene como relleno)
        WITH childMember, parentMember,
             (CASE WHEN p1 ENDS WITH "0" THEN substring(p1, 0, size(p1)-1) ELSE p1 END) AS p2,
             (CASE WHEN c1 ENDS WITH "0" THEN substring(c1, 0, size(c1)-1) ELSE c1 END) AS c2

        // 4. Limpieza Nivel 3: Quitamos el segundo cero a la derecha (si lo tiene como relleno)
        WITH childMember, parentMember,
             (CASE WHEN p2 ENDS WITH "0" THEN substring(p2, 0, size(p2)-1) ELSE p2 END) AS parentCode,
             (CASE WHEN c2 ENDS WITH "0" THEN substring(c2, 0, size(c2)-1) ELSE c2 END) AS childCode

        // 5. FILTRO CRÍTICO: Validamos que ambos sean numéricos, que el hijo empiece con el padre y sea estrictamente más largo (más dígitos activos)
        WHERE parentCode =~ '^[0-9.]+$' 
        AND childCode =~ '^[0-9.]+$'
        AND childCode STARTS WITH parentCode
        AND size(childCode) > size(parentCode)

        // 6. Buscamos el prefijo más largo (el padre más específico)
        WITH childMember, parentMember, size(parentCode) as prefLen
        ORDER BY prefLen DESC

        // 7. Nos quedamos con el mejor candidato por cada miembro hijo
        WITH childMember, collect(parentMember)[0] as bestParent

        // 8. Creamos la estructura jerárquica
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
