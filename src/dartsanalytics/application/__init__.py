"""Application Service tier (docs §10 resolution: ``UI -> Application
Service -> Repository Interface -> Local DB Repository``).

Services in this package are the only layer a UI is meant to call for
anything that touches persistence. They depend on the Repository
Interfaces (dartsanalytics.db.repositories.interfaces) and the
UnitOfWork (dartsanalytics.db.unit_of_work), never on sqlite3 directly,
so persistence can be swapped without touching this code.
"""
