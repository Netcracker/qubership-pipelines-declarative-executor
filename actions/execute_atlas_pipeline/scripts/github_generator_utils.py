from __future__ import annotations

import configparser
import os
import re
import yaml  # pip install pyyaml
import copy

import logging

logger = logging.getLogger(__name__)

## configure yaml module
# https://stackoverflow.com/questions/45004464/yaml-dump-adding-unwanted-newlines-in-multiline-strings/45004775
yaml.add_representer(str,
        lambda dumper, data: dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|' if '\n' in data else None),
        yaml.SafeDumper)
## HC remove 'on/off' bool remapping
yaml.SafeDumper.yaml_implicit_resolvers.pop('o', None)


def traverse(obj: dict | list, path: list = [], traverse_nested_lists: bool = True):
    for k, v in obj.items() if isinstance(obj, dict) else enumerate(obj):
        if isinstance(v, dict) or (traverse_nested_lists and isinstance(v, list)):
            for kv in traverse(v, path + [k], traverse_nested_lists):
                yield kv
        else:
            yield path + [k], v


def parse_params_from_string(content: str):
    if not content:
        return {}
    ini = configparser.ConfigParser()
    ini.optionxform = lambda s: s  # do not convert to lowercase
    ini.read_string('[none]\n' + content)  # unnamed sections are only supported in Python 3.13+
    return {k: (v[:-1] if v.endswith(';') else v) for k, v in ini.items('none')}


def cast_to_string(value, value_for_none=''):
    if isinstance(value, str): return value
    if value is None: return value_for_none
    if isinstance(value, bool): return 'true' if value else 'false'
    return str(value)


VAR_PATTERN = re.compile(
        r'\$\{(?:env:)?([a-zA-Z_]\w*)\}|\$([a-zA-Z_]\w*)')  # handle optional prefix 'env:' to workaround A PROBLEM
VAR_MAX_NESTING_LEVEL = 100
def substitute_string(known_vars=None, *, var_name=None, expression=None) -> str:
    if known_vars is None:
        known_vars = os.environ

    if var_name is not None:  # calculate variable
        expression = known_vars.get(var_name)
        description = f"variable '{var_name}'"
    else:  # calculate expression
        description = f"expression '{expression}'"

    if not isinstance(expression, str):
        return cast_to_string(expression)
    value = expression
    for _ in range(VAR_MAX_NESTING_LEVEL):
        value, repl_n = re.subn(VAR_PATTERN, lambda m: cast_to_string(known_vars.get(m[1] or m[2])), value)
        if repl_n:
            logger.debug(f"Calculated {description}: {value}")
        else:
            return value
    raise ValueError(f"Variables substitution exceeded {VAR_MAX_NESTING_LEVEL} nesting levels for {description}")


def recursive_merge(source_dict: dict, target_dict: dict):
    """Recursively adds all keys from target_dict to a copy of source_dict"""
    source = copy.deepcopy(source_dict)
    target = copy.deepcopy(target_dict)
    if target is None:
        return source
    for key, value in target.items():
        if key in source and isinstance(source[key], dict) and isinstance(value, dict):
            source[key] = recursive_merge(source[key], value)
        else:
            source[key] = value
    return source


def inflate_dict(source_dict: dict):
    """Converts dict with composite keys (like 'parent2.parent1.child_object') into corresponding inflated dict"""
    result = copy.deepcopy(source_dict)
    for key in list(result.keys()):
        value = result[key]
        if isinstance(value, dict):
            value = inflate_dict(value)
        if '.' in key:
            if (key_parts := [part for part in key.split('.') if part]) and len(key_parts) > 1:
                for key_index in range(len(key_parts)):
                    changed_dict = result
                    for i in range(key_index):
                        changed_dict = changed_dict[key_parts[i]]
                    if key_parts[key_index] in changed_dict and isinstance(changed_dict[key_parts[key_index]], dict):
                        if key_index == len(key_parts) - 1:
                            changed_dict[key_parts[key_index]] = recursive_merge(changed_dict[key_parts[key_index]], value)
                    else:
                        changed_dict[key_parts[key_index]] = value if key_index == len(key_parts) - 1 else {}
                result.pop(key)
        else:
            result[key] = value
    return result


UNSAFE_JOBNAME_CHARS_PATTERN = re.compile(r'[^\w\-_]')
def get_safe_gh_jobname(s: str):
    return re.sub(UNSAFE_JOBNAME_CHARS_PATTERN, '_', s)


def get_id_or_name(atlas_stage: dict):
    if 'id' in atlas_stage:
        return atlas_stage.get('id')
    else:
        return atlas_stage.get('name')
