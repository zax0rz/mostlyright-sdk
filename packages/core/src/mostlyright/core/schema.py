"""Declarative schema framework for tradewinds.

Defines the ``Schema`` base class, ``ColumnSpec`` description records, and
``SchemaRegistration`` audit-trail container. These are the shape contracts
that the Validator, KnowledgeView, and adapter layers consume.

See ``docs/design.md`` §A (canonical schemas), §BB.3 (settlement schema),
§BB.4 (audit log API), and §J (allow_source_drift reason-string semantics).

TimePoint will eventually wrap timestamp handling; this module accepts raw
``datetime`` objects for now and validates that they are timezone-aware.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    import pandas as pd


__all__ = ["ColumnSpec", "Schema", "SchemaRegistration"]


#: Canonical dtype tags. Strings (not Python types) so schemas can be
#: serialized to JSON / parquet metadata without losing the original
#: declaration intent.
_CANONICAL_DTYPES: frozenset[str] = frozenset(
    {
        "string",
        "float64",
        "int64",
        "timestamp_utc",
        "date",
        "bool",
        "enum",
    }
)


@dataclass(frozen=True)
class ColumnSpec:
    """Description of a single column in a ``Schema``.

    Attributes:
        name: Column name as it appears in the canonical (metric) projection.
        dtype: One of the canonical dtype tags. ``"enum"`` requires
            ``enum_values`` to be populated.
        units: Free-form unit label (``"celsius"``, ``"meters"``, ``"kt"``)
            or ``None`` for dimensionless columns.
        nullable: Whether the column may contain ``NaN``/``NULL`` values.
        enum_values: Allowed values when ``dtype == "enum"``. Must be ``None``
            for non-enum columns.
        notes: Free-form documentation surfaced in catalog metadata.
    """

    name: str
    dtype: str
    units: str | None
    nullable: bool
    enum_values: tuple[str, ...] | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        if self.dtype not in _CANONICAL_DTYPES:
            raise ValueError(
                f"ColumnSpec {self.name!r}: dtype {self.dtype!r} is not a "
                f"canonical dtype. Allowed: {sorted(_CANONICAL_DTYPES)}"
            )
        if self.dtype == "enum" and not self.enum_values:
            raise ValueError(
                f"ColumnSpec {self.name!r}: dtype='enum' requires non-empty enum_values"
            )
        if self.dtype != "enum" and self.enum_values is not None:
            raise ValueError(
                f"ColumnSpec {self.name!r}: enum_values only valid for "
                f"dtype='enum' (got dtype={self.dtype!r})"
            )


def _utc_now() -> datetime:
    """Wall-clock UTC timestamp for audit entries."""
    return datetime.now(tz=UTC)


def _require_tz_aware(ts: datetime, field_name: str) -> datetime:
    """Stub for the eventual TimePoint dependency.

    Schemas require timezone-aware datetimes; naive timestamps would silently
    cross DST boundaries on the way to event-time / knowledge-time joins.
    """
    if not isinstance(ts, datetime):
        raise TypeError(f"{field_name} must be a datetime, got {type(ts).__name__}")
    if ts.tzinfo is None or ts.tzinfo.utcoffset(ts) is None:
        raise ValueError(f"{field_name} must be timezone-aware (got naive datetime {ts!r})")
    return ts


@dataclass
class SchemaRegistration:
    """Audit-trail container produced by ``Schema.register(...)``.

    Records the (source, retrieved_at range, row count) provenance of a
    training-time pull and accumulates an append-only audit log. The audit
    log captures source-drift opt-outs and reproducibility-audit outcomes
    per ``docs/design.md`` §BB.4.

    Validator wires audit events in via :meth:`_append_audit`; this module
    intentionally does not import Validator (it is implemented elsewhere).

    **Audit-log seam (contract — read this).** The single-underscore prefix
    on :attr:`_audit` and :meth:`_append_audit` denotes *module-private with
    one cross-module writer*: the Validator (a sibling module) calls
    ``_append_audit`` to record ``source_drift_allowed`` and
    ``temporal_drift_audit`` events. Any caller OTHER than
    :meth:`Schema.register` or the Validator that invokes ``_append_audit``
    — or any direct mutation of ``_audit`` — is a contract violation: the
    audit log is meant to be append-only and stamped by trusted writers
    only. The list is intentionally not frozen so the Validator can append
    without indirection; this is the explicit seam, documented here so
    code review can catch unauthorised callers.

    **Deferred to v0.1.1:** ``volatility_warning`` (per design §B/§P,
    surfaced by ``catalog_search`` and flagged on schemas whose registered
    rows fall within the 30-day volatile window of ``iem.archive``) will
    land as an attribute on this dataclass populated by the catalog
    adapter at registration time. v0.1.0 carries no such attribute.
    """

    schema: type[Schema]
    source: str
    retrieved_at_min: datetime
    retrieved_at_max: datetime
    rows: int
    # ``_audit``: module-private. Validator is the only sanctioned external
    # writer (via ``_append_audit``) — see class docstring "Audit-log seam".
    _audit: list[dict[str, Any]] = field(default_factory=list)

    def audit_log(self) -> list[dict[str, Any]]:
        """Return a defensive copy of the chronologically-ordered audit log.

        Both the outer list and each inner entry are shallow-copied so
        callers cannot mutate stored entries (e.g.
        ``reg.audit_log()[0]["event"] = "tampered"`` is a no-op against
        the underlying log). The list contains dict entries with at
        minimum ``event`` and ``ts`` (ISO-8601 UTC) keys. See
        :meth:`_append_audit` for the supported event vocabulary.
        """
        return [dict(entry) for entry in self._audit]

    def _append_audit(self, event: str, **kwargs: Any) -> None:
        """Append a new audit entry. **Validator-only hook** (plus
        :meth:`Schema.register` which seeds the ``registered`` event).

        Calling ``_append_audit`` from anywhere else — application code,
        notebooks, downstream catalog adapters — is a contract violation;
        the audit log is meant to be a trusted provenance record and only
        ``Schema.register`` and the Validator are sanctioned writers. See
        the :class:`SchemaRegistration` class docstring for the full seam
        contract.

        Supported event vocabulary (per design §BB.4):

        - ``registered`` — appended once by :meth:`Schema.register`.
        - ``source_drift_allowed`` — appended by ``Validator.validate_dataframe``
          when ``allow_source_drift=<reason>`` is passed.
        - ``temporal_drift_audit`` — appended by
          ``Validator.validate_dataframe`` when
          ``assert_retrieved_at_range=...`` is passed.

        Extra ``kwargs`` are merged into the audit entry; a UTC ``ts`` is
        stamped automatically if the caller does not supply one. Timestamps
        are serialised as ISO-8601 strings so the audit log is JSON-safe.
        """
        entry: dict[str, Any] = {"event": event}
        ts = kwargs.pop("ts", None)
        if ts is None:
            ts = _utc_now()
        if isinstance(ts, datetime):
            entry["ts"] = ts.isoformat()
        else:
            entry["ts"] = ts
        entry.update(kwargs)
        self._audit.append(entry)


class Schema:
    """Declarative schema base class.

    Subclasses declare:

    - :attr:`schema_id` — stable identifier (``"schema.observation.v1"``).
    - :attr:`COLUMNS` — ordered list of :class:`ColumnSpec`.
    - :attr:`IMPERIAL_RENAMES` (optional) — metric → imperial column-name
      map; columns not mentioned keep their metric name.

    The base class is intentionally light: no I/O, no DataFrame coupling.
    Validator and adapter layers consume :attr:`COLUMNS` to perform their
    work; ``Schema`` itself only holds the contract.
    """

    schema_id: ClassVar[str] = ""
    COLUMNS: ClassVar[list[ColumnSpec]] = []
    IMPERIAL_RENAMES: ClassVar[dict[str, str]] = {}

    # -- introspection ----------------------------------------------------

    @classmethod
    def column_names(cls, mode: str = "metric") -> list[str]:
        """Return the column names in declaration order for the given mode.

        ``mode="metric"`` returns the canonical names declared in
        :attr:`COLUMNS`. ``mode="imperial"`` applies :attr:`IMPERIAL_RENAMES`
        (columns absent from the rename map keep their metric name).

        Raises:
            ValueError: if ``mode`` is not ``"metric"`` or ``"imperial"``.
        """
        if mode == "metric":
            return [c.name for c in cls.COLUMNS]
        if mode == "imperial":
            renames = cls.IMPERIAL_RENAMES
            return [renames.get(c.name, c.name) for c in cls.COLUMNS]
        raise ValueError(f"mode must be 'metric' or 'imperial' (got {mode!r})")

    @classmethod
    def column(cls, name: str) -> ColumnSpec:
        """Look up a :class:`ColumnSpec` by its (metric) name.

        Raises:
            KeyError: if ``name`` does not name a declared column.
        """
        for spec in cls.COLUMNS:
            if spec.name == name:
                return spec
        raise KeyError(
            f"{cls.__name__}: no column named {name!r}. Declared columns: "
            f"{[c.name for c in cls.COLUMNS]}"
        )

    # -- registration -----------------------------------------------------

    @classmethod
    def register(
        cls,
        source: str,
        retrieved_at: datetime,
        rows: int,
    ) -> SchemaRegistration:
        """Register this schema against a concrete pull.

        Records the ``source`` and ``retrieved_at`` provenance and produces
        a fresh :class:`SchemaRegistration` carrying the audit log. The
        ``registered`` event is appended automatically.

        .. note::

           **v0.1.0 is a per-call factory.** Every call returns a brand-new
           :class:`SchemaRegistration` with an independent audit log; there
           is no cross-call registry that deduplicates by
           ``(schema_id, source)`` or merges audit events across pulls.

           Design §BB.4 describes an audit log that persists with the
           schema across calls; that **persistence model lands in v0.1.1**
           alongside the catalog adapter, which owns the (schema, source)
           keying and on-disk storage decisions (parquet metadata, JSON
           sidecar). Callers in v0.1.0 that need a long-lived registration
           must hold onto the returned object themselves.

           Track at: <ticket>

        Args:
            source: Source identity in ``"<source>.<endpoint>"`` form
                (``"iem.archive"``, ``"awc.live"``).
            retrieved_at: Wall-clock timestamp of the pull that produced
                the rows. MUST be timezone-aware.
            rows: Row count after schema validation.

        Raises:
            TypeError: if ``source`` is not ``str``, ``retrieved_at`` is
                not a ``datetime``, or ``rows`` is not ``int``.
            ValueError: if ``source`` is empty, ``retrieved_at`` is naive,
                or ``rows`` is negative.
        """
        if not isinstance(source, str):
            raise TypeError(f"source must be str (got {type(source).__name__})")
        if not source:
            raise ValueError("source must be a non-empty string")
        if not isinstance(rows, int) or isinstance(rows, bool):
            raise TypeError(f"rows must be int (got {type(rows).__name__})")
        if rows < 0:
            raise ValueError(f"rows must be >= 0 (got {rows})")
        retrieved_at = _require_tz_aware(retrieved_at, "retrieved_at")
        # Normalise to UTC so the stored range and audit-log ISO strings
        # are consistent regardless of caller-side tzinfo. Equality with
        # the input timestamp is preserved (datetime equality respects tz).
        retrieved_at = retrieved_at.astimezone(UTC)

        reg = SchemaRegistration(
            schema=cls,
            source=source,
            retrieved_at_min=retrieved_at,
            retrieved_at_max=retrieved_at,
            rows=rows,
        )
        reg._append_audit(
            "registered",
            ts=retrieved_at,
            source=source,
            rows=rows,
        )
        return reg

    @classmethod
    def from_dataframe(
        cls,
        df: pd.DataFrame,
        source: str,
        retrieved_at: datetime,
    ) -> Schema:
        """Infer a schema from a DataFrame (BYO data path). Deferred to v0.1.1.

        Per ``docs/design.md`` Premise 5 (and §"Layer responsibilities"):
        schemas can be constructed declaratively (subclasses of :class:`Schema`)
        OR inferred from a sample DataFrame. The declarative path ships in
        v0.1.0; the inference path (this method) ships in v0.1.1.

        Track at: <ticket>
        """
        raise NotImplementedError(
            "Schema.from_dataframe is deferred to v0.1.1; use declarative subclasses for v0.1.0."
        )
