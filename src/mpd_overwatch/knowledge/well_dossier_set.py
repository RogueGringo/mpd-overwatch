"""Container for all dossiers from one well."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from mpd_overwatch.knowledge.dossier import ChannelDossier
from mpd_overwatch.knowledge.rig_state import RigState, StateTransition
from mpd_overwatch.knowledge.stand_detector import Stand


@dataclass
class WellDossierSet:
    """All channel dossiers for a single well, plus state timeline."""

    dossiers: Dict[str, ChannelDossier] = field(default_factory=dict)
    states: Optional[List[RigState]] = None
    transitions: List[StateTransition] = field(default_factory=list)
    stands: List[Stand] = field(default_factory=list)
    source: str = ""

    def get(self, wits_id: str) -> Optional[ChannelDossier]:
        """Look up dossier by WITS ID."""
        return self.dossiers.get(wits_id)

    def get_by_canonical(self, canonical: str) -> Optional[ChannelDossier]:
        """Look up dossier by canonical name."""
        for d in self.dossiers.values():
            if d.canonical == canonical:
                return d
        return None

    def channels_with_artifacts(self) -> List[ChannelDossier]:
        """Return all dossiers that have artifact profiles."""
        return [d for d in self.dossiers.values() if d.artifacts]

    def channels_in_domain(self, domain_name: str) -> List[ChannelDossier]:
        """Return all dossiers in a physics domain."""
        return [d for d in self.dossiers.values() if d.physics_domain.value == domain_name]
