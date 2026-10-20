"""M2.5: the hub gives each subscriber the run's backlog, then every new message, until closed."""

import asyncio
import uuid

from app.core.hub import Hub, Message
from app.routers.stream import frames

RUN = uuid.uuid4()
COMMUNITY = uuid.uuid4()


def test_message_frames_follow_the_sse_format() -> None:
    frame = Message(3, "event", {"seq": 1, "type": "appear"}).frame()
    assert frame == 'id: 3\nevent: event\ndata: {"seq":1,"type":"appear"}\n\n'


def test_backlog_then_live_messages_then_close() -> None:
    async def scenario() -> tuple[list[int], list[int | None]]:
        hub = Hub()
        hub.open(RUN, COMMUNITY, [("event", {"seq": 1}), ("event", {"seq": 2})])
        backlog, queue = hub.subscribe(RUN)
        hub.publish(RUN, [("event", {"seq": 3})])
        hub.close(RUN)
        received = [await queue.get(), await queue.get()]
        return (
            [message.id for message in backlog],
            [message.id if message else None for message in received],
        )

    backlog_ids, received = asyncio.run(scenario())
    assert backlog_ids == [1, 2]
    assert received == [3, None]


def test_an_unopened_run_is_skipped_and_a_reopened_one_starts_from_its_backlog() -> None:
    hub = Hub()
    hub.publish(RUN, [("event", {"seq": 1})])
    assert hub.channel(RUN) is None
    channel = hub.open(RUN, COMMUNITY, [("event", {"seq": 1})])
    assert hub.open(RUN, COMMUNITY, [("event", {"seq": 9})]) is channel
    assert [message.data for message in channel.log] == [{"seq": 1}]


def test_frames_send_the_backlog_pings_when_idle_and_end_on_close() -> None:
    async def scenario() -> list[str]:
        hub = Hub()
        hub.open(RUN, COMMUNITY, [("event", {"seq": 1})])
        backlog, queue = hub.subscribe(RUN)
        out: list[str] = []
        stream = frames(hub, RUN, backlog, queue, ping_s=0.01)
        out.append(await anext(stream))
        out.append(await anext(stream))  # nothing new: a keep-alive comment
        hub.publish(RUN, [("alert", {"id": "a1"})])
        out.append(await anext(stream))
        hub.close(RUN)
        out += [frame async for frame in stream]
        return out

    out = asyncio.run(scenario())
    assert out[0].startswith("id: 1\nevent: event\n")
    assert out[1] == ": ping\n\n"
    assert out[2].startswith("id: 2\nevent: alert\n")
    assert len(out) == 3
