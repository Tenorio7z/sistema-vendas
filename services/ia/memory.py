"""Memória curta, local e limitada para as conversas do assistente."""

from collections import defaultdict, deque
from threading import RLock


class ConversationMemory:
    def __init__(self, max_messages=8):
        self._messages = defaultdict(lambda: deque(maxlen=max_messages))
        self._lock = RLock()

    def get(self, key):
        with self._lock:
            return list(self._messages.get(key, ()))

    def add_turn(self, key, user_message, assistant_message):
        with self._lock:
            conversation = self._messages[key]
            conversation.append({"role": "user", "content": user_message})
            conversation.append({"role": "assistant", "content": assistant_message})

    def clear(self, key):
        with self._lock:
            self._messages.pop(key, None)


memory = ConversationMemory()
