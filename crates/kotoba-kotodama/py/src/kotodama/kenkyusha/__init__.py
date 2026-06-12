"""kenkyusha — AI research-frontier explorer LangGraph package.

Graph id: ``kenkyusha-research-loop``
Server : ``60-apps/etzhayyim-project-kenkyusha/lg/`` (uvicorn lg_kenkyusha.server:app)
Schema : Alembic 20260514_0001 (vertex_kenkyusha_{discipline,frontier,hypothesis,evidence})

The Pregel super-step loop implements Google co-scientist's 6 roles
(Generation / Reflection / Ranking / Evolution / Proximity / Meta-review)
inspired by scienceearth.org's Publish→Bid→Decompose→Challenge→Select
problem lifecycle. State is persisted to RisingWave via asyncpg; the
LangGraph checkpointer schema is ``lg_kenkyusha_checkpoint``.
"""
