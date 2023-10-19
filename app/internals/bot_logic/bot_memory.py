import copy
import typing
from collections import OrderedDict

from aiogram.dispatcher.storage import BaseStorage


def safe_copy_dict(old_d: typing.Dict = None, non_copy_keys: list = None):
    if old_d is None:
        return None
    new_d = {}
    for key, value in old_d.items():
        if non_copy_keys is not None and key in non_copy_keys:
            new_d[key] = value
        else:
            new_d[key] = copy.deepcopy(value)
    return new_d


class LRUCache:

    def __init__(self, capacity: int, on_remove: typing.Callable = None):
        self.capacity = capacity
        self.cache = OrderedDict()
        self.on_remove = on_remove

    def get(self, key):
        if key in self.cache:
            value = self.cache.pop(key)
            self.cache[key] = value
            return value
        return None

    def put(self, key, value):
        if key in self.cache:
            self.cache.pop(key)
        elif len(self.cache) >= self.capacity:
            rem_key, rem_value = self.cache.popitem(last=False)
            if self.on_remove is not None:
                self.on_remove(rem_key)
        self.cache[key] = value

    def __getitem__(self, key):
        return self.get(key)

    def __setitem__(self, key, value):
        self.put(key, value)

    def __contains__(self, key):
        return key in self.cache


class LRUMutableMemoryStorage(BaseStorage):
    """
    In-memory based states storage.

    Uses PriorityQueue to remove oldest users when capacity overflows max_entries
    """

    async def wait_closed(self):
        pass

    async def close(self):
        self.data.cache.clear()

    def __init__(self, max_entries: int,
                 non_copy_keys: list = None,
                 on_auto_remove: typing.Callable = None):
        self.max_entries = max_entries
        self.non_copy_keys = non_copy_keys
        self.data = LRUCache(capacity=max_entries, on_remove=on_auto_remove)

    def resolve_address(self, chat, user):
        chat_id, user_id = map(str, self.check_address(chat=chat, user=user))

        if chat_id not in self.data:
            self.data[chat_id] = {}
        if user_id not in self.data[chat_id]:
            self.data[chat_id][user_id] = {'state': None, 'data': {}, 'bucket': {}}

        return chat_id, user_id

    async def get_state(self, *,
                        chat: typing.Union[str, int, None] = None,
                        user: typing.Union[str, int, None] = None,
                        default: typing.Optional[str] = None) -> typing.Optional[str]:
        chat, user = self.resolve_address(chat=chat, user=user)
        return self.data[chat][user].get("state", self.resolve_state(default))

    async def get_data(self, *,
                       chat: typing.Union[str, int, None] = None,
                       user: typing.Union[str, int, None] = None,
                       default: typing.Optional[str] = None) -> typing.Dict:
        chat, user = self.resolve_address(chat=chat, user=user)

        if chat not in self.data:
            self.data[chat] = {}
        if user not in self.data[chat]:
            self.data[chat][user] = {'state': None, 'data': {}, 'bucket': {}}

        return safe_copy_dict(self.data[chat][user]['data'], self.non_copy_keys)

    async def update_data(self, *,
                          chat: typing.Union[str, int, None] = None,
                          user: typing.Union[str, int, None] = None,
                          data: typing.Dict = None, **kwargs):
        if data is None:
            data = {}
        chat, user = self.resolve_address(chat=chat, user=user)
        self.data[chat][user]['data'].update(data, **kwargs)

    async def set_state(self, *,
                        chat: typing.Union[str, int, None] = None,
                        user: typing.Union[str, int, None] = None,
                        state: typing.AnyStr = None):
        chat, user = self.resolve_address(chat=chat, user=user)
        self.data[chat][user]['state'] = self.resolve_state(state)

    async def set_data(self, *,
                       chat: typing.Union[str, int, None] = None,
                       user: typing.Union[str, int, None] = None,
                       data: typing.Dict = None):
        chat, user = self.resolve_address(chat=chat, user=user)
        self.data[chat][user]['data'] = safe_copy_dict(data, self.non_copy_keys)
        self._cleanup(chat, user)

    async def reset_state(self, *,
                          chat: typing.Union[str, int, None] = None,
                          user: typing.Union[str, int, None] = None,
                          with_data: typing.Optional[bool] = True):
        await self.set_state(chat=chat, user=user, state=None)
        if with_data:
            await self.set_data(chat=chat, user=user, data={})
        self._cleanup(chat, user)

    def has_bucket(self):
        return True

    async def get_bucket(self, *,
                         chat: typing.Union[str, int, None] = None,
                         user: typing.Union[str, int, None] = None,
                         default: typing.Optional[dict] = None) -> typing.Dict:
        chat, user = self.resolve_address(chat=chat, user=user)
        return safe_copy_dict(self.data[chat][user]['bucket'])

    async def set_bucket(self, *,
                         chat: typing.Union[str, int, None] = None,
                         user: typing.Union[str, int, None] = None,
                         bucket: typing.Dict = None):
        chat, user = self.resolve_address(chat=chat, user=user)
        self.data[chat][user]['bucket'] = safe_copy_dict(bucket)
        self._cleanup(chat, user)

    async def update_bucket(self, *,
                            chat: typing.Union[str, int, None] = None,
                            user: typing.Union[str, int, None] = None,
                            bucket: typing.Dict = None, **kwargs):
        if bucket is None:
            bucket = {}
        chat, user = self.resolve_address(chat=chat, user=user)
        self.data[chat][user]['bucket'].update(bucket, **kwargs)

    def _cleanup(self, chat, user):
        chat, user = self.resolve_address(chat=chat, user=user)
        if self.data[chat][user] == {'state': None, 'data': {}, 'bucket': {}}:
            del self.data.cache[chat][user]
        if not self.data[chat]:
            del self.data.cache[chat]
