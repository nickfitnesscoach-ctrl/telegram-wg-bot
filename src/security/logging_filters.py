import logging, re

class SecretFilter(logging.Filter):
    _pat = re.compile(r'(\d{9,}:[A-Za-z0-9_\-]{20,})')
    def filter(self, record):
        record.msg = self._pat.sub("[BOT_TOKEN]", str(record.msg))
        return True
