"""Граф связей (M2.2, D27): производный индекс сущностей и связей модели в Postgres.

Система записи — git с YAML; индекс пересобирается по коммитам и сборкам и может быть удалён без потерь.
`db` — подключение и схема, `extract` — словарь сущностей и связей и извлечение из модели, `index` —
индексатор, `query` — окрестность, «где используется», поиск, сводка.
"""

from skelcad.graph.db import Graph
from skelcad.graph.extract import KINDS, RELATIONS, Ent, Rel, extract_project, extract_variant
from skelcad.graph.index import Indexer

__all__ = ["Graph", "Indexer", "KINDS", "RELATIONS", "Ent", "Rel", "extract_project", "extract_variant"]
