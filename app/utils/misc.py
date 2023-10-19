import datetime
import re

time_regexp = re.compile(
    r'^((?P<days>[\.\d]+?)d)?((?P<hours>[\.\d]+?)h)?((?P<minutes>[\.\d]+?)m)?((?P<seconds>[\.\d]+?)s)?$')


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


def percent_trim_list(array, percent):
    trim_len = round(len(array) * percent)
    return array[:len(array) - trim_len]


def strfdelta(tdelta, format):
    d = {"D": tdelta.days}
    hours, rem = divmod(tdelta.seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    d["H"] = '{:02d}'.format(hours)
    d["M"] = '{:02d}'.format(minutes)
    d["S"] = '{:02d}'.format(seconds)
    return format.format(**d)


def clean_text(text):
    # Удаляем все символы кроме разрешенных
    text = re.sub(r'[^\w\s\.?!\:\;\(\)\[\]%\*\/\\#\-$]', '', text)
    # Удаляем все символы, которые повторяются подряд 3 и больше раз, кроме пробелов и переносов строк
    text = re.sub(r'([^\s])\1{2,}', r'\1\1', text)
    # Удаляем повторяющиеся пробелы и переносы строк
    text = re.sub(r'(\s)\1{2,}', r'\1\1', text)
    return text


if __name__ == '__main__':
    delta = parse_timedelta('3d')
    new = datetime.datetime.now() + delta
    print(delta, new)
    print(clean_text('Привет. Hello.   123. @*#*(@. --[][]----. adddddddbddda\n1. Test.\n2.ABCD\n\n\nTest3'))
    print(strfdelta(datetime.timedelta(days=207, seconds=11090, microseconds=334920),
                    format='{D} дней {H} часов {M} минут'))

