import asyncio
import copy
import datetime
import re
import typing
from collections import OrderedDict

from aiogram.dispatcher.storage import BaseStorage


time_regexp = re.compile(
    r'^((?P<days>[\.\d]+?)d)?((?P<hours>[\.\d]+?)h)?((?P<minutes>[\.\d]+?)m)?((?P<seconds>[\.\d]+?)s)?$')


def safe_copy_dict(old_d: typing.Dict = None):
    if old_d is None:
        return None
    new_d = {}
    for key, value in old_d.items():
        try:
            new_d[key] = copy.deepcopy(value)
        except TypeError:
            new_d[key] = value
    return new_d


class LRUCache:

    def __init__(self, capacity):
        self.capacity = capacity
        self.cache = OrderedDict()

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
            self.cache.popitem(last=False)  # Удаляем самый старый элемент

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

    def __init__(self, max_entries: int):
        self.max_entries = max_entries
        self.data = LRUCache(capacity=max_entries)

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

        return safe_copy_dict(self.data[chat][user]['data'])

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
        self.data[chat][user]['data'] = safe_copy_dict(data)
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


class TypingBlock(object):

    def __init__(self, chat):
        self.chat = chat
        self.typing_task = None

    async def __aenter__(self):

        async def typing_cycle():
            try:
                while True:
                    await self.chat.do("typing")
                    await asyncio.sleep(2)
            except asyncio.CancelledError:
                pass

        self.typing_task = asyncio.create_task(typing_cycle())

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.typing_task:
            self.typing_task.cancel()


def parse_timedelta(time_str) -> datetime.timedelta:
    """
    Parse a time string e.g. (2h13m) into a timedelta object.

    Modified from virhilo's answer at https://stackoverflow.com/a/4628148/851699

    :param time_str: A string identifying a duration.  (eg. 2h13m)
    :return datetime.timedelta: A datetime.timedelta object
    """
    parts = time_regexp.match(time_str)
    assert parts is not None, "Could not parse any time information from '{}'.  Examples of valid strings: '8h', " \
                              "'2d8h5m20s', '2m4s'".format(time_str)
    time_params = {name: float(param) for name, param in parts.groupdict().items() if param}
    return datetime.timedelta(**time_params)


if __name__ == '__main__':
    delta = parse_timedelta('3d')
    new = datetime.datetime.now() + delta
    print(delta, new)
