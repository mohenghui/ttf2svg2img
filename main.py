from . import fonts2svg
from . import scrap


def convert_font_to_svg(font: str, glyphs: str = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ') -> dict:
    return fonts2svg.mainInMemory(['-c', '000000', '-g', ','.join(glyphs), font])


def get_glyphs(font: str) -> dict:
    svgs = convert_font_to_svg(font)
    return scrap.get_svg_paths(svgs)
