from collections import UserDict
from functools import reduce


class UtilsDictionary:
    @staticmethod
    def _safe_cast_to_int(val):
        try:
            return int(val)
        except ValueError:
            return val

    @staticmethod
    def split_path(path:str):
        return path.split('.')

    @staticmethod
    def getitem_by_path(target_dict, path):  # corresponds to dict.__getitem__
        if isinstance(path, str):
            path = UtilsDictionary.split_path(path)
        return reduce(lambda obj, k: obj[UtilsDictionary._safe_cast_to_int(k) if isinstance(obj, list) else k],
                      path,
                      target_dict)

    @staticmethod
    def get_by_path(target_dict, path, def_value=None):  # corresponds to dict.get
        try:
            return UtilsDictionary.getitem_by_path(target_dict, path)
        except (IndexError, KeyError):
            return def_value

    @staticmethod
    def _extend_list(lst, lst_path, key):
        if not isinstance(key, int):
            raise ValueError(f"Key type mismatch for list at path '{lst_path}', key '{key}': expected int, got {type(key)}")
        required_len = key + 1
        if (extend_by := required_len - len(lst)) > 0:
            lst.extend([None] * extend_by)

    @staticmethod
    def _create_container_for_key(key):
        try:
            int(key)
            return []
        except Exception:
            return {}

    @staticmethod
    def setitem_by_path(target_dict, path, value):  # corresponds to dict.__setitem__
        if isinstance(path, str):
            path = UtilsDictionary.split_path(path)
        current_obj = target_dict
        current_path = []
        for key, next_key in zip(path, path[1:]):
            if isinstance(current_obj, list):
                int_key = UtilsDictionary._safe_cast_to_int(key)
                UtilsDictionary._extend_list(current_obj, current_path, int_key)
                next_obj = current_obj[int_key]
                if next_obj is None:
                    next_obj = UtilsDictionary._create_container_for_key(next_key)
                    current_obj[int_key] = next_obj
            else:
                next_obj = current_obj.setdefault(key, UtilsDictionary._create_container_for_key(next_key))
            current_obj = next_obj
            current_path.append(key)
        key = path[-1]
        if isinstance(current_obj, list):
            key = UtilsDictionary._safe_cast_to_int(key)
            UtilsDictionary._extend_list(current_obj, current_path, key)
        current_obj[key] = value
        return target_dict


class HierarchicalDict(UserDict):
    """A minimum implementation of dict-like class with hierarchical keys, to work in ChainMap get and set operations"""

    def __getitem__(self, key): return UtilsDictionary.getitem_by_path(self.data, key)
    def get(self, key, default=None): return UtilsDictionary.get_by_path(self.data, key, default)
    def __setitem__(self, key, item): return UtilsDictionary.setitem_by_path(self.data, key, item)
    def __contains__(self, key):
        try:
            self[key]
        except KeyError:
            return False
        return True
    @staticmethod
    def wrap(data: dict):
        """Unlike constructors, this method does not copy data, but creates an instance backed by the given dict"""
        instance = HierarchicalDict()
        instance.data = data
        return instance