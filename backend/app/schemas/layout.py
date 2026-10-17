from collections import Counter
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.db.models import NodeKind, NodeStatus, ZoneKind
from app.schemas.common import Code

Point = tuple[float, float]


class CommunityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
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


class LayoutOut(BaseModel):
    community: CommunityOut
    zones: list[ZoneOut]
    nodes: list[NodeOut]
    links: list[LinkOut]


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


class LayoutFile(BaseModel):
    """A community layout as a file. References are codes, never database IDs (D-75)."""

    model_config = ConfigDict(extra="forbid")

    community: LayoutFileCommunity
    zones: list[LayoutFileZone]
    nodes: list[LayoutFileNode]
    links: list[LayoutFileLink]

    @model_validator(mode="after")
    def check_references(self) -> Self:
        problems: list[str] = []
        for label, codes in (("zone", [z.code for z in self.zones]), ("node", self.node_codes)):
            problems += [f"duplicate {label} code {c}" for c, n in Counter(codes).items() if n > 1]
        zones, nodes = {z.code for z in self.zones}, set(self.node_codes)
        problems += [
            f"node {n.code} names unknown zone {n.zone}"
            for n in self.nodes
            if n.zone is not None and n.zone not in zones
        ]
        seen: dict[tuple[str, str], bool] = {}
        for link in self.links:
            pair = (link.from_node, link.to_node)
            label = f"link {link.from_node} -> {link.to_node}"
            if link.from_node == link.to_node:
                problems.append(f"{label} joins a node to itself")
            problems += [f"{label} names unknown node {end}" for end in pair if end not in nodes]
            if link.travel_min_s > link.travel_max_s:
                problems.append(f"{label} has travel_min_s above travel_max_s")
            reverse = seen.get(pair[::-1])
            if pair in seen or (reverse is not None and (reverse or link.bidirectional)):
                problems.append(f"{label} duplicates another link")
            seen[pair] = link.bidirectional
        if problems:
            raise ValueError("; ".join(problems))
        return self

    @property
    def node_codes(self) -> list[str]:
        return [n.code for n in self.nodes]
