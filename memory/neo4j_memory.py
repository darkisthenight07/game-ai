# memory/neo4j_memory.py — Neo4j long-term memory backend
import os
from neo4j import GraphDatabase

URI      = os.getenv("NEO4J_URI",      "neo4j+s://ef06bcb1.databases.neo4j.io")
USER     = os.getenv("NEO4J_USER",     "ef06bcb1")
PASSWORD = os.getenv("NEO4J_PASSWORD", "D0Mf4L0y1q5w78ntAfZnHKqDAYWCNn2Jq-Bj8x_G6pQ")

driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))


def neo4j_write(char: str, relation: str, target: str, value: int, context: str) -> None:
    """Write or update a relationship edge between two characters in Neo4j."""
    with driver.session() as session:
        session.run(
            """
            MERGE (a:Character {name:$char})
            MERGE (b:Character {name:$target})
            MERGE (a)-[r:%(rel)s]->(b)
            SET r.level    = coalesce(r.level, 0) + $value,
                r.contexts = coalesce(r.contexts, []) + $context
            """ % {"rel": relation},
            char=char, target=target, value=value, context=context,
        )


def neo4j_read(char: str) -> list[str]:
    """Read all relationship edges for a character from Neo4j."""
    with driver.session() as session:
        result = session.run(
            """
            MATCH (c:Character {name:$char})-[r]->(o)
            RETURN type(r) as rel, o.name as target, r.level as level, r.contexts as context
            """,
            char=char,
        )
        return [
            f"{char} {r['rel']} {r['target']} (level:{r['level']}) ctx:{(r['context'] or [])[-3:]}"
            for r in result
        ]
