from __future__ import annotations


class ColorUtils:

    SUCCESS_COLOR = "GREEN"
    FAILURE_COLOR = "RED"
    COLOR_CODES = {
        'BLUE': '\033[38;5;67m',  # steel_blue
        'GREEN': '\033[38;5;79m',  # light_sea_green
        'ORANGE': '\033[38;5;172m',  # orange
        'RED': '\033[38;5;131m',  # indian_red
        'VIOLET': '\033[38;5;162m',  # medium_violet_red
        'RESET': '\033[0m',
    }

    @staticmethod
    def with_color(message: str, color: str) -> str:
        if color in ColorUtils.COLOR_CODES:
            return f"{ColorUtils.COLOR_CODES[color]}{message}{ColorUtils.COLOR_CODES['RESET']}"
        else:
            return message
