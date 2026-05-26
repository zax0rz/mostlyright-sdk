Mostlyright Python SDK
======================

Local-first SDK for prediction-market weather settlement research.

The canonical public surface is :func:`mostlyright.research`, which joins
NWS CLI climate observations with METAR observation aggregates (AWC, IEM,
GHCNh) into a settlement-ready Pandas DataFrame. See the per-module pages
below for the full reference.

.. autosummary::
   :toctree: api
   :recursive:

   mostlyright
   mostlyright.research
   mostlyright.discover
   mostlyright.live
   mostlyright.snapshot
   mostlyright.core
   mostlyright.weather
   mostlyright.markets

Indices
=======

* :ref:`genindex`
* :ref:`modindex`
