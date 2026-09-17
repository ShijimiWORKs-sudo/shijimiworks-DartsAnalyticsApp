"""Repository layer (docs §10 resolution): ``UI -> Application Service ->
Repository Interface -> Local DB Repository``.

``interfaces`` defines the Repository Interface tier as ``typing.Protocol``
classes — the Application Service layer (``dartsanalytics.application``)
depends only on these, never on SQLite directly, so a future non-SQLite
Local DB Repository (or an in-memory fake for tests) can be swapped in
without touching application code.

``sqlite_repositories`` is the one Local DB Repository implementation this
project ships today.  ``unit_of_work`` composes the concrete repositories
behind a single connection/transaction so a caller gets atomic
multi-repository writes (e.g. "save a session together with its rounds and
throws, or save nothing").
"""
