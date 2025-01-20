try:
    from .runner import bps

    bps.enable()
except ImportError:
    pass
