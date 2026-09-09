"""Regressors, behind one port.

The learner was LightGBM everywhere until a measurement showed it was the weakest of
the three libraries on this data by a wide margin, so it is no longer hardcoded. Each
library is an adapter behind `Regressor`, and callers name the ones they want.
"""

from taxiout.models.base import Regressor, blend, build

__all__ = ["Regressor", "blend", "build"]
