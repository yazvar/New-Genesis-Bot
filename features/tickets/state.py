from dataclasses import dataclass
from datetime import datetime, timezone
import json

from config.paths import DATA_DIR

STATE_FILE = DATA_DIR / "tickets.json"


@dataclass
class PanelMessage:
    channel_id: int
    message_id: int
    webhook_id: int | None = None


@dataclass
class TicketRecord:
    ticket_id: int
    channel_id: int
    message_id: int
    category: str
    creator_id: int
    creator_name: str
    created_at: datetime
    staff_id: int | None = None
    staff_name: str | None = None
    closed_at: datetime | None = None

    @property
    def is_open(self) -> bool:
        return self.closed_at is None

    @property
    def is_accepted(self) -> bool:
        return self.staff_id is not None


class TicketStore:
    """Хранит панель тикетов и открытые обращения."""

    def __init__(self) -> None:
        self._panel: PanelMessage | None = None
        self._tickets: dict[int, TicketRecord] = {}
        self._next_ticket_id: int = 1
        self._load()

    @property
    def panel(self) -> PanelMessage | None:
        return self._panel

    @property
    def tickets(self) -> list[TicketRecord]:
        return list(self._tickets.values())

    @property
    def open_tickets(self) -> list[TicketRecord]:
        return [ticket for ticket in self._tickets.values() if ticket.is_open]

    @property
    def next_ticket_id(self) -> int:
        return self._next_ticket_id

    def get_ticket(self, channel_id: int) -> TicketRecord | None:
        return self._tickets.get(channel_id)

    def count_open_by_user(self, user_id: int) -> int:
        return sum(
            1
            for ticket in self._tickets.values()
            if ticket.is_open and ticket.creator_id == user_id
        )

    def set_panel(
        self,
        channel_id: int,
        message_id: int,
        webhook_id: int | None = None,
    ) -> None:
        self._panel = PanelMessage(
            channel_id=channel_id,
            message_id=message_id,
            webhook_id=webhook_id,
        )
        self._save()

    def add_ticket(
        self,
        *,
        channel_id: int,
        message_id: int,
        category: str,
        creator_id: int,
        creator_name: str,
    ) -> TicketRecord:
        record = TicketRecord(
            ticket_id=self._next_ticket_id,
            channel_id=channel_id,
            message_id=message_id,
            category=category,
            creator_id=creator_id,
            creator_name=creator_name,
            created_at=datetime.now(timezone.utc),
        )
        self._next_ticket_id += 1
        self._tickets[channel_id] = record
        self._save()
        return record

    def accept_ticket(
        self,
        channel_id: int,
        staff_id: int,
        staff_name: str,
    ) -> TicketRecord | None:
        record = self._tickets.get(channel_id)
        if record is None or not record.is_open or record.is_accepted:
            return None

        record.staff_id = staff_id
        record.staff_name = staff_name
        self._save()
        return record

    def close_ticket(self, channel_id: int) -> TicketRecord | None:
        record = self._tickets.get(channel_id)
        if record is None or not record.is_open:
            return None

        record.closed_at = datetime.now(timezone.utc)
        self._save()
        return record

    def remove_ticket(self, channel_id: int) -> None:
        if channel_id in self._tickets:
            del self._tickets[channel_id]
            self._save()

    def _load(self) -> None:
        if not STATE_FILE.exists():
            return

        try:
            raw = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return

        self._next_ticket_id = int(raw.get("next_ticket_id", 1))

        panel = raw.get("panel")
        if panel:
            self._panel = PanelMessage(
                channel_id=int(panel["channel_id"]),
                message_id=int(panel["message_id"]),
                webhook_id=(
                    int(panel["webhook_id"])
                    if panel.get("webhook_id") is not None
                    else None
                ),
            )

        for item in raw.get("tickets", []):
            record = TicketRecord(
                ticket_id=int(item["ticket_id"]),
                channel_id=int(item["channel_id"]),
                message_id=int(item["message_id"]),
                category=str(item["category"]),
                creator_id=int(item["creator_id"]),
                creator_name=str(item["creator_name"]),
                created_at=datetime.fromisoformat(item["created_at"]),
                staff_id=(
                    int(item["staff_id"]) if item.get("staff_id") is not None else None
                ),
                staff_name=(
                    str(item["staff_name"])
                    if item.get("staff_name") is not None
                    else None
                ),
                closed_at=(
                    datetime.fromisoformat(item["closed_at"])
                    if item.get("closed_at") is not None
                    else None
                ),
            )
            self._tickets[record.channel_id] = record

    def _save(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        payload: dict = {
            "next_ticket_id": self._next_ticket_id,
            "panel": None,
            "tickets": [],
        }

        if self._panel:
            payload["panel"] = {
                "channel_id": self._panel.channel_id,
                "message_id": self._panel.message_id,
                "webhook_id": self._panel.webhook_id,
            }

        payload["tickets"] = [
            {
                "ticket_id": ticket.ticket_id,
                "channel_id": ticket.channel_id,
                "message_id": ticket.message_id,
                "category": ticket.category,
                "creator_id": ticket.creator_id,
                "creator_name": ticket.creator_name,
                "created_at": ticket.created_at.isoformat(),
                "staff_id": ticket.staff_id,
                "staff_name": ticket.staff_name,
                "closed_at": (
                    ticket.closed_at.isoformat() if ticket.closed_at is not None else None
                ),
            }
            for ticket in self._tickets.values()
        ]

        STATE_FILE.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
