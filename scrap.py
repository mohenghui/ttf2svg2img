from . import fonts2svg
from bs4 import BeautifulSoup


def get_svg_paths(svgs: dict) -> dict:
    paths = {}
    for symbol, svg in svgs.items():
        paths[symbol] = BeautifulSoup(svg, 'html.parser').find('path').get('d')
    return paths
