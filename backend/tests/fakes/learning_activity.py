from datetime import timedelta


class InMemoryLearningActivities:
    def __init__(self):
        self.items = {}

    def save(self, activity):
        self.items[(str(activity.owner_id), str(activity.item_id))] = activity

    def recent_by_owner(self, owner_id, limit):
        owned = [item for item in self.items.values() if item.owner_id == owner_id]
        return tuple(sorted(owned, key=lambda item: item.last_opened_at, reverse=True)[:limit])


class SteppingClock:
    """Advance one minute per reading so each recorded open has a distinct time."""

    def __init__(self, start):
        self._next = start

    def now(self):
        current = self._next
        self._next = current + timedelta(minutes=1)
        return current
