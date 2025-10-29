def get_command_class_from_module(module_path: str, cmd_name: str):
    import sys, importlib, re
    from pathlib import Path

    module_path = str(Path(module_path).resolve())
    if module_path not in sys.path:
        sys.path.insert(0, module_path)

    main_py_path = Path(module_path) / "__main__.py"
    with open(main_py_path, 'r') as f:
        main_content = f.read()

    match = re.search(r'import\s+(\w+)\.__main__', main_content)
    if not match:
        raise ValueError("Could not find main module in __main__.py")
    main_module_name = match.group(1)

    main_module_main_py = Path(module_path) / main_module_name / "__main__.py"
    with open(main_module_main_py, 'r') as f:
        main_module_content = f.read()

    command_info = _extract_command_info(main_module_content, cmd_name)
    if not command_info:
        raise ValueError(f"Command '{cmd_name}' not found in {main_module_name}.__main__.py")

    module = importlib.import_module(command_info['module'])
    return getattr(module, command_info['class_name'])


def _extract_command_info(main_module_content: str, cmd: str):
    import re
    lines = main_module_content.split('\n')
    for i, line in enumerate(lines):
        if f'@cli.command("{cmd}")' in line or f"@cli.command('{cmd}')" in line:
            function_body = []
            for j in range(i + 1, min(i + 10, len(lines))):
                if lines[j].strip().startswith('def '):
                    func_start = j
                    for k in range(func_start + 1, min(func_start + 20, len(lines))):
                        current_line = lines[k]
                        if current_line.strip() and not current_line[0].isspace():
                            break
                        function_body.append(current_line)
                    break
            func_body_str = '\n'.join(function_body)
            import_match = re.search(r'from\s+([\w\.]+)\s+import\s+(\w+)', func_body_str)
            if import_match:
                module_name = import_match.group(1)
                class_name = import_match.group(2)
                if re.search(rf'{class_name}\s*\(', func_body_str):
                    return {
                        'module': module_name,
                        'class_name': class_name
                    }
    return None