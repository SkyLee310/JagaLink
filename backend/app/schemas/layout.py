from collections import Counter
from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, model_validator

from app.db.models import NodeKind, NodeStatus, ZoneKind
from app.engine.layout import LinkSpec, NodeSpec, check_layout
from app.schemas.common import Code

Point = tuple[float, float]
Name = Annotated[str, Field(min_length=1, max_length=80)]
Heading = Annotated[float, Field(ge=0, lt=360)]
TravelSeconds = Annotated[int, Field(gt=0, le=86_400)]
Distance = Annotated[float, Field(gt=0)]


class CommunityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    map_image_url: str | None
    scale_m_per_px: float
    timezone: str


class ZoneOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    kind: ZoneKind
    polygon: list[Point]


class NodeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    kind: NodeKind
    name: str
    x: float
    y: float
    heading_deg: float
    status: NodeStatus
    zone_id: UUID | None


class LinkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    from_node_id: UUID
    to_node_id: UUID
    travel_min_s: int
    travel_max_s: int
    bidirectional: bool
    distance_m: float | None


class LayoutOut(BaseModel):
    community: CommunityOut
    zones: list[ZoneOut]
    nodes: list[NodeOut]
    links: list[LinkOut]


# Editing (F1). Zones are seeded and read-only in Phase 1 (D-64), so only nodes and links change.


class NodeIn(BaseModel):
    """A node in a saved layout. A new node's ID comes from the client, so links can name it."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    code: Code
    kind: NodeKind
    name: Name
    x: FiniteFloat
    y: FiniteFloat
    heading_deg: Heading = 0
    status: NodeStatus = "online"
    zone_id: UUID | None = None


class NodeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID | None = None
    code: Code
    kind: NodeKind
    name: Name
    x: FiniteFloat
    y: FiniteFloat
    heading_deg: Heading = 0
    status: NodeStatus = "online"
    zone_id: UUID | None = None


class NodePatch(BaseModel):
    """Only the fields sent change; `zone_id: null` clears the zone."""

    model_config = ConfigDict(extra="forbid")

    code: Code | None = None
    kind: NodeKind | None = None
    name: Name | None = None
    x: FiniteFloat | None = None
    y: FiniteFloat | None = None
    heading_deg: Heading | None = None
    status: NodeStatus | None = None
    zone_id: UUID | None = None


class LinkIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID | None = None
    from_node_id: UUID
    to_node_id: UUID
    travel_min_s: TravelSeconds
    travel_max_s: TravelSeconds
    bidirectional: bool = True
    distance_m: Distance | None = None


class LinkPatch(BaseModel):
    """Only the fields sent change. The ends of a link are fixed: delete it and add another."""

    model_config = ConfigDict(extra="forbid")

    travel_min_s: TravelSeconds | None = None
    travel_max_s: TravelSeconds | None = None
    bidirectional: bool | None = None
    distance_m: Distance | None = None


class LayoutIn(BaseModel):
    """The whole editable layout, saved in one transaction (PUT /communities/{id}/layout)."""

    model_config = ConfigDict(extra="forbid")

    nodes: list[NodeIn]
    links: list[LinkIn]


# Layout files (export, import and the seed). References are codes, never database IDs (D-75).


class LayoutFileCommunity(BaseModel):
    slug: Code
    name: str
    map_image_url: str | None = None
    scale_m_per_px: float = Field(gt=0)
    timezone: str = "Asia/Kuala_Lumpur"


class LayoutFileZone(BaseModel):
    code: Code
    name: str
    kind: ZoneKind
    polygon: list[Point] = Field(min_length=3)


class LayoutFileNode(BaseModel):
    code: Code
    kind: NodeKind
    name: str
    x: float
    y: float
    heading_deg: float = Field(default=0, ge=0, lt=360)
    status: NodeStatus = "online"
    zone: Code | None = None


class LayoutFileLink(BaseModel):
    from_node: Code
    to_node: Code
    travel_min_s: int = Field(gt=0)
    travel_max_s: int = Field(gt=0)
    bidirectional: bool = True
    distance_m: float | None = Field(
        default=None, gt=0, description="Walking distance along the streets (D-69)"
    )


class NormalRoute(BaseModel):
    """A route residents normally take, as node codes in walking order (D-53)."""

    name: str
    nodes: list[Code] = Field(min_length=2)


class LayoutFile(BaseModel):
    """A community layout as a file. References are codes, never database IDs (D-75)."""

    model_config = ConfigDict(extra="forbid")

    community: LayoutFileCommunity
    zones: list[LayoutFileZone]
    nodes: list[LayoutFileNode]
    links: list[LayoutFileLink]
    normal_routes: list[NormalRoute] = []

    @model_validator(mode="after")
    def check_references(self) -> Self:
        zone_codes = [zone.code for zone in self.zones]
        problems = [f"duplicate zone code {c}" for c, n in Counter(zone_codes).items() if n > 1]
        problems += [
            problem.message
            for problem in check_layout(
                [NodeSpec(node.code, node.code, node.zone) for node in self.nodes],
                [
                    LinkSpec(
                        link.from_node,
                        link.to_node,
                        link.travel_min_s,
                        link.travel_max_s,
                        link.bidirectional,
                    )
                    for link in self.links
                ],
                zone_codes,
            )
        ]
        if problems:
            raise ValueError("; ".join(problems))
        return self

    @property
    def node_codes(self) -> list[str]:
        return [n.code for n in self.nodes]
