class EsphomeError(Exception):
    pass

class _Core:
    address_cache = None
    dashboard = False

CORE = _Core()
