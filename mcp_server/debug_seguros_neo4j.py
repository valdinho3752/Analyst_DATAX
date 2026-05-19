from neo4j import GraphDatabase

driver = GraphDatabase.driver('bolt://neo4j_graph:7687', auth=('neo4j', 'testpassword'))

with driver.session() as s:
    res = s.run('MATCH (m:Member {table: "S_BOAPS_44_000612"})-[r:CHILD_OF]->(p:Member) RETURN m.name, p.name LIMIT 20')
    count = 0
    print("--- RELACIONES CHILD_OF EN S_BOAPS_44_000612 ---")
    for r in res:
        print(f"[{r[0]}] -> [{r[1]}]")
        count += 1
    print(f"Muestra de relaciones: {count}")
    
    print("\n--- BUSCANDO EL NODO '101 DISPONIBLE' ---")
    res2 = s.run('MATCH (m:Member {table: "S_BOAPS_44_000612"}) WHERE m.name CONTAINS "101 DISPONIBLE" OPTIONAL MATCH path=(m)-[:CHILD_OF*]->(root) RETURN m.name, [n in nodes(path) | n.name] as lineage')
    for r in res2:
        print(f"Nodo: {r[0]} | Linaje: {r[1]}")

driver.close()
