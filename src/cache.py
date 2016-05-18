import hashlib
import os
import os.path


class FileCache:
    def __init__(self, dir):
        self.dir = dir

    def has(self, key):
        os.path.isfile(self._file_name_of(key))

    def get(self, key):
        file = open(self._file_name_of(key), 'r')
        s = file.read()
        file.close()
        return s

    def set(self, key, value):
        file = open(self._file_name_of(key), 'w')
        file.write(value)
        file.close()

    def remove(self, key):
        os.remove(self._file_name_of(key))

    def _file_name_of(self, key):
        return self.dir + "/" + hashlib.sha256(key).hexdigest() + ".cache"
