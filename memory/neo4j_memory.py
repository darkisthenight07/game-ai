# neo4j_memory.py — Neo4j long-term memory, scoped per player

import logging
import os
import re
from typing import Optional

from dotenv import load_dotenv
from neo4j import GraphDatabase, Driver
from neo4j.exceptions import Neo4jError, ServiceUnavailable

load_dotenv()

log = logging.getLogger(__name__)

# ── Connection management ─────────────────────────────────────────────────────

_driver: Optional[Driver] = None

# Allowlist for relationship types: uppercase letters and underscores only.
# Extend this set as the story demands new relation types.
_VALID_REL_TYPES: frozenset[str] = frozenset({
    "INTERACTED_WITH",
    "FEARS",
    "TRUSTS",
    "DISTRUSTS",
    "HATES",
    "RESPECTS",
    "IS_CURIOUS_ABOUT",
    "KNOWS_SECRET_OF",
    "HAS_WITNESSED",
    "WARNED",
    "THREATENED",
    "AIDED",
    "BETRAYED",
})

_REL_TYPE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")


def _get_driver() -> Driver:
    """Return the shared driver, (re-)creating it if necessary."""
    global _driver
    if _driver is None:
        uri      = os.getenv("NEO4J_URI")
        user     = os.getenv("NEO4J_USER")
        password = os.getenv("NEO4J_PASSWORD")
        if not all([uri, user, password]):
            raise EnvironmentError(
                "NEO4J_URI, NEO4J_USER, and NEO4J_PASSWORD must all be set in the environment."
            )
        _driver = GraphDatabase.driver(uri, auth=(user, password))
    return _driver


def _validate_rel_type(relation: str) -> str:
    """
    Validate that a relationship type is safe to embed in a Cypher query.

    Neo4j does not support parameterised relationship type names, so we must
    validate strictly before interpolation.  Only uppercase letters, digits,
    and underscores are allowed; the type must also exist in _VALID_REL_TYPES.
    Raises ValueError on failure.
    """
    rel = relation.strip().upper()
    if not _REL_TYPE_PATTERN.match(rel):
        raise ValueError(
            f"Invalid relationship type '{relation}'. "
            "Must match [A-Z][A-Z0-9_]* (uppercase letters, digits, underscores)."
        )
    if rel not in _VALID_REL_TYPES:
        # Accept it but log a warning — the game can still run; just not ideal
        log.warning(
            "Relationship type '%s' is not in the known allowlist. "
            "Add it to _VALID_REL_TYPES if it is intentional.", rel
        )
    return rel


def _ensure_constraints(driver: Driver) -> None:
    """
    Create uniqueness constraints on first use.
    Safe to call multiple times — Neo4j ignores duplicate constraint creation.
    """
    with driver.session() as session:
        session.run(
            "CREATE CONSTRAINT player_id_unique IF NOT EXISTS "
            "FOR (p:Player) REQUIRE p.id IS UNIQUE"
        )
        session.run(
            "CREATE CONSTRAINT character_scope_unique IF NOT EXISTS "
            "FOR (c:Character) REQUIRE (c.name, c.player_id) IS UNIQUE"
        )


_constraints_ensured = False


def _init() -> Driver:
    global _constraints_ensured
    driver = _get_driver()
    if not _constraints_ensured:
        try:
            _ensure_constraints(driver)
            _constraints_ensured = True
        except (Neo4jError, ServiceUnavailable) as exc:
            log.warning("Could not ensure Neo4j constraints: %s", exc)
    return driver


# ── Public API ────────────────────────────────────────────────────────────────

def neo4j_write(
    player_id: str,
    char: str,
    relation: str,
    target: str,
    value: int,
    context: str,
) -> None:
    """
    Write or update a directed relationship edge between two characters in Neo4j,
    scoped to a specific player.

    The Player node is merged first; each Character node is keyed on
    (name, player_id) so different players have independent graphs.
    """
    rel = _validate_rel_type(relation)
    driver = _init()

    # Cypher: relationship type cannot be parameterised — we validated `rel` above.
    cypher = f"""
        MERGE (p:Player {{id: $player_id}})

        MERGE (a:Character {{name: $char,   player_id: $player_id}})
        MERGE (b:Character {{name: $target, player_id: $player_id}})

        MERGE (p)-[:HAS_CHARACTER]->(a)
        MERGE (p)-[:HAS_CHARACTER]->(b)

        MERGE (a)-[r:{rel}]->(b)
        SET   r.level    = coalesce(r.level, 0) + $value,
              r.contexts = coalesce(r.contexts, []) + $context,
              r.updated_at = datetime()
    """
    try:
        with driver.session() as session:
            session.run(
                cypher,
                player_id=player_id,
                char=char,
                target=target,
                value=value,
                context=context[:300],          # guard against huge context strings
            )
    except (Neo4jError, ServiceUnavailable) as exc:
        log.error("neo4j_write failed for player=%s char=%s: %s", player_id, char, exc)


def neo4j_read(player_id: str, char: str) -> list[str]:
    """
    Read all outgoing relationship edges for (player_id, character) from Neo4j.
    Returns an empty list (not an exception) if the DB is unreachable.
    """
    driver = _init()
    cypher = """
        MATCH (c:Character {name: $char, player_id: $player_id})-[r]->(o:Character)
        RETURN type(r)    AS rel,
               o.name     AS target,
               r.level    AS level,
               r.contexts AS contexts
        ORDER BY r.level DESC
    """
    try:
        with driver.session() as session:
            result = session.run(cypher, player_id=player_id, char=char)
            rows = []
            for record in result:
                recent_ctx = (record["contexts"] or [])[-3:]
                rows.append(
                    f"{char} {record['rel']} {record['target']} "
                    f"(level:{record['level']}) ctx:{recent_ctx}"
                )
            return rows
    except (Neo4jError, ServiceUnavailable) as exc:
        log.error("neo4j_read failed for player=%s char=%s: %s", player_id, char, exc)
        return []


def neo4j_close() -> None:
    """Close the driver gracefully (call on game exit)."""
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None
