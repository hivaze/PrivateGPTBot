import enum
from copy import deepcopy
from dataclasses import dataclass
from typing import List


class ChatRole(enum.Enum):
    SYSTEM = 0
    USER = 1
    ASSISTANT = 2
    FUNCTION = 3


@dataclass
class ChatMessage:
    role: ChatRole = None
    text: str = None


@dataclass
class FunctionResponseMessage(ChatMessage):
    name: str = None


@dataclass
class FunctionCallMessage(ChatMessage):
    name: str = None
    arguments: dict = None


class ChatHistory:

    def __init__(self, system_prompt: str = None):
        self._chat_history: List[ChatMessage] = []
        self.system_message = ChatMessage(role=ChatRole.SYSTEM, text=system_prompt) if system_prompt else None

    def add_message(self, chat_message: ChatMessage):
        self._chat_history.append(chat_message)

    def drop_last_arc(self):
        last_message = self._chat_history.pop()
        while type(last_message) != ChatMessage or last_message.role != ChatRole.USER:
            last_message = self._chat_history.pop()

    def remove_function_responses(self):
        self._chat_history = list(filter(lambda x: not isinstance(x, FunctionResponseMessage), self._chat_history))

    @property
    def chat_history(self):
        return deepcopy(self._chat_history)

    @chat_history.setter
    def chat_history(self, new_history: List[ChatMessage]):
        self._chat_history = new_history

    def __len__(self):
        return len(self._chat_history)
