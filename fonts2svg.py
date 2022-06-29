#!/usr/bin/env python

# Copyright 2016 Adobe. All rights reserved.

"""
Generates a set of SVG glyph files from one or more fonts and hex colors
for each of them. The fonts' format can be either OpenType, TrueType, WOFF,
or WOFF2.
"""

import argparse
import os
import re
import sys
import shutil
from fontTools import ttLib
from fontTools.pens.basePen import BasePen
from fontTools.pens.transformPen import TransformPen

from utils import (
    create_folder,
    create_nested_folder,
    final_message,
    get_gnames_to_save_in_nested_folder,
    get_output_folder_path,
    split_comma_sequence,
    validate_font_paths,
    write_file,
)


class SVGPen(BasePen):

    def __init__(self, glyphSet):
        BasePen.__init__(self, glyphSet)
        self.d = u''
        self._lastX = self._lastY = None

    def _moveTo(self, pt):
        ptx, pty = self._isInt(pt)
        self.d += u'M{} {}'.format(ptx, pty)
        self._lastX, self._lastY = pt

    def _lineTo(self, pt):
        ptx, pty = self._isInt(pt)
        if (ptx, pty) == (self._lastX, self._lastY):
            return
        elif ptx == self._lastX:
            self.d += u'V{}'.format(pty)
        elif pty == self._lastY:
            self.d += u'H{}'.format(ptx)
        else:
            self.d += u'L{} {}'.format(ptx, pty)
        self._lastX, self._lastY = pt

    def _curveToOne(self, pt1, pt2, pt3):
        pt1x, pt1y = self._isInt(pt1)
        pt2x, pt2y = self._isInt(pt2)
        pt3x, pt3y = self._isInt(pt3)
        self.d += u'C{} {} {} {} {} {}'.format(pt1x, pt1y, pt2x, pt2y,
                                               pt3x, pt3y)
        self._lastX, self._lastY = pt3

    def _qCurveToOne(self, pt1, pt2):
        pt1x, pt1y = self._isInt(pt1)
        pt2x, pt2y = self._isInt(pt2)
        self.d += u'Q{} {} {} {}'.format(pt1x, pt1y, pt2x, pt2y)
        self._lastX, self._lastY = pt2

    def _closePath(self):
        self.d += u'Z'
        self._lastX = self._lastY = None

    def _endPath(self):
        self._closePath()

    @staticmethod
    def _isInt(tup):
        return [int(flt) if (flt).is_integer() else flt for flt in tup]


def processFonts(font_paths_list, hex_colors_list, outputFolderPath, options):
    

    # Load the fonts and collect their glyph sets
    for fontPath in font_paths_list: #遍历字体文件夹
        glyphSetsList = []
        allGlyphNamesList = []
        try:
            font = ttLib.TTFont(fontPath)
            gSet = font.getGlyphSet()
            glyphSetsList.append(gSet)
            allGlyphNamesList.append(gSet.keys())
            font.close()#关闭打开

        except ttLib.TTLibError:
            print(f"ERROR: {fontPath} cannot be processed.",
                  file=sys.stderr)
            return 1

        # Define the list of glyph names to convert to SVG
        if options.gnames_to_generate: #如果有定义名单
            glyphNamesList = sorted(set(options.gnames_to_generate))
        else:
            if options.glyphsets_union:
                glyphNamesList = sorted(
                    set.union(*map(set, allGlyphNamesList))) #按union排序
            else:
                glyphNamesList = sorted(
                    set.intersection(*map(set, allGlyphNamesList)))
                # Extend the list with additional glyph names
                if options.gnames_to_add:
                    glyphNamesList.extend(options.gnames_to_add)
                    # Remove any duplicates and sort
                    glyphNamesList = sorted(set(glyphNamesList))

        # Remove '.notdef'
        if '.notdef' in glyphNamesList: #如果没定义在里面就移除
            glyphNamesList.remove('.notdef')

        # Confirm that there's something to process
        if not glyphNamesList: #如果没有，就是不能提供字体
            print("The fonts and options provided can't produce any SVG files.",
                file=sys.stdout)
            return 1

        # Define the list of glyph names to skip
        glyphNamesToSkipList = [] #定义要跳过的list
        if options.gnames_to_exclude:
            glyphNamesToSkipList.extend(options.gnames_to_exclude)

        # Determine which glyph names need to be saved in a nested folder
        glyphNamesToSaveInNestedFolder = get_gnames_to_save_in_nested_folder(
            glyphNamesList)

        nestedFolderPath = None
        filesSaved = 0

        viewbox = viewbox_settings( #viewbox的设置
            font_paths_list[0],
            options.adjust_view_box_to_glyph
        )

        # Generate the SVGs
        for gName in glyphNamesList:

            svgStr = (u"""<svg xmlns="http://www.w3.org/2000/svg" """
                    u"""viewBox="{}">\n""".format(viewbox))
            
            for index, gSet in enumerate(glyphSetsList):
                # Skip glyphs that don't exist in the current font,
                # or that were requested to be skipped
                if gName not in gSet.keys() or gName in glyphNamesToSkipList:
                    continue

                pen = SVGPen(gSet)
                tpen = TransformPen(pen, (1.0, 0.0, 0.0, -1.0, 0.0, 0.0))
                glyph = gSet[gName]
                glyph.draw(tpen)
                d = pen.d
                # Skip glyphs with no contours
                if not len(d):
                    continue

                hex_str = hex_colors_list[index]
                opc = ''
                if len(hex_str) != 6:
                    opcHex = hex_str[6:]
                    hex_str = hex_str[:6]
                    if opcHex.lower() != 'ff':
                        opc = ' opacity="{:.2f}"'.format(int(opcHex, 16) / 255)#不透明

                svgStr += u'\t<path{} fill="#{}" d="{}"/>\n'.format(
                    opc, hex_str, d) #
            svgStr += u'</svg>'

            # Skip saving files that have no paths
            if '<path' not in svgStr:
                continue

            # Create the output folder.
            # This may be necessary if the folder was not provided.
            # The folder is made this late in the process because
            # only now it's clear that's needed.
            create_folder(outputFolderPath)

            # Create the nested folder, if there are conflicting glyph names.

            if gName in glyphNamesToSaveInNestedFolder:
                folderPath = create_nested_folder(nestedFolderPath,
                                                outputFolderPath)
            else:
                folderPath = outputFolderPath
            save_dir=folderPath+'/'+os.path.splitext(os.path.basename(fontPath))[0]
            if not os.path.exists(save_dir):
                os.mkdir(save_dir)
            # else:
            #     shutil.rmtree(save_dir,ignore_errors=True)
            svgFilePath = os.path.join(save_dir,gName+ '.svg')
            write_file(svgFilePath, svgStr)
            filesSaved += 1

        font.close()
        final_message(filesSaved)
    return 0


def processFontsInMemory(font_paths_list, hex_colors_list, outputFolderPath, options):
    glyphSetsList = []
    allGlyphNamesList = []

    # Load the fonts and collect their glyph sets
    for fontPath in font_paths_list:
        try:
            font = ttLib.TTFont(fontPath)
            gSet = font.getGlyphSet()
            glyphSetsList.append(gSet)
            allGlyphNamesList.append(gSet.keys())
            font.close()

        except ttLib.TTLibError:
            print(f"ERROR: {fontPath} cannot be processed.",
                  file=sys.stderr)
            return 1

    # Define the list of glyph names to convert to SVG
    if options.gnames_to_generate:
        glyphNamesList = sorted(set(options.gnames_to_generate))
    else:
        if options.glyphsets_union:
            glyphNamesList = sorted(
                set.union(*map(set, allGlyphNamesList)))
        else:
            glyphNamesList = sorted(
                set.intersection(*map(set, allGlyphNamesList)))
            # Extend the list with additional glyph names
            if options.gnames_to_add:
                glyphNamesList.extend(options.gnames_to_add)
                # Remove any duplicates and sort
                glyphNamesList = sorted(set(glyphNamesList))

    # Remove '.notdef'
    if '.notdef' in glyphNamesList:
        glyphNamesList.remove('.notdef')

    # Confirm that there's something to process
    if not glyphNamesList:
        print("The fonts and options provided can't produce any SVG files.",
              file=sys.stdout)
        return 1

    # Define the list of glyph names to skip
    glyphNamesToSkipList = []
    if options.gnames_to_exclude:
        glyphNamesToSkipList.extend(options.gnames_to_exclude)
    # options.adjust_view_box_to_glyph=True
    viewbox = viewbox_settings(
        font_paths_list[0],
        options.adjust_view_box_to_glyph
    )

    svgStrings = {}

    # Generate the SVGs
    for gName in glyphNamesList:
        svgStr = (u"""<svg xmlns="http://www.w3.org/2000/svg" """
                  u"""viewBox="{}">\n""".format(viewbox))

        for index, gSet in enumerate(glyphSetsList):
            # Skip glyphs that don't exist in the current font,
            # or that were requested to be skipped
            if gName not in gSet.keys() or gName in glyphNamesToSkipList:
                continue

            pen = SVGPen(gSet)
            tpen = TransformPen(pen, (1.0, 0.0, 0.0, -1.0, 0.0, 0.0))
            glyph = gSet[gName]
            glyph.draw(tpen)
            d = pen.d
            # Skip glyphs with no contours
            if not len(d):
                continue

            hex_str = hex_colors_list[index]
            opc = ''
            if len(hex_str) != 6:
                opcHex = hex_str[6:]
                hex_str = hex_str[:6]
                if opcHex.lower() != 'ff':
                    opc = ' opacity="{:.2f}"'.format(int(opcHex, 16) / 255)

            svgStr += u'\t<path{} fill="#{}" d="{}"/>\n'.format(
                opc, hex_str, d)
        svgStr += u'</svg>'

        # Skip saving files that have no paths
        if '<path' not in svgStr:
            continue

        svgStrings[gName] = svgStr

    # font.close()
    return svgStrings


def viewbox_settings(font_path, adjust_view_box_to_glyph):
    try:
        head = ttLib.TTFont(font_path)["head"]
        if adjust_view_box_to_glyph:
            # it looks like compared to viewbox in the head table
            # the yMin and yMax are inverted
            # x = head.xMin
            x = 0
            # y = -head.yMax
            y = -800
            # width = head.xMax - head.xMin #
            width = 1024
            # height = head.yMax - head.yMin
            height = 1024
            return """{} {} {} {}""".format(x, y, width, height)
        else:
            # Gather the fonts' UPM. For simplicity,
            # it's assumed that all fonts have the same UPM value.
            # If fetching the UPM value fails, default to 1000.
            upm = head.unitsPerEm
            return """0 -{} {} {}""".format(upm, upm, upm)
    except KeyError:
        upm = 1000
        return """0 -{} {} {}""".format(upm, upm, upm)


RE_HEXCOLOR = re.compile(r"^(?=[a-fA-F0-9]*$)(?:.{6}|.{8})$")


def validate_hex_values(hex_str):
    hex_values = split_comma_sequence(hex_str)
    for hex_val in hex_values:
        if not RE_HEXCOLOR.match(hex_val):
            raise argparse.ArgumentTypeError(
                "{} is not a valid hex color.".format(hex_val))
    return hex_values


def get_options(args):
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter,
        description=__doc__
    )
    parser.add_argument(
        '-c',
        metavar='HEX_VALUES',
        dest='colors_list',
        type=validate_hex_values,
        default=['000000'],
        help='comma-separated list of hex colors in RRGGBBAA format.\n'
             'The alpha value (AA) is optional.'
    )
    parser.add_argument(
        '-o',
        metavar='FOLDER_PATH',
        dest='output_folder_path',
        default="./save_svg",
        help='path to folder for outputting the SVG files to.'
    )
    parser.add_argument(
        '-g',
        metavar='GLYPH_NAMES',
        dest='gnames_to_generate',
        type=split_comma_sequence,
        default=[],
        help='comma-separated sequence of glyph names to make SVG files from.'
    )
    parser.add_argument(
        '-a',
        metavar='GLYPH_NAMES',
        dest='gnames_to_add',
        type=split_comma_sequence,
        default=[],
        help='comma-separated sequence of glyph names to add.'
    )
    parser.add_argument(
        '-x',
        metavar='GLYPH_NAMES',
        dest='gnames_to_exclude',
        type=split_comma_sequence,
        default=[],
        help='comma-separated sequence of glyph names to exclude.'
    )
    parser.add_argument(
        '-u',
        # action='store_true',
        dest='glyphsets_union',
        type=bool,
        default=True,
        help="do union (instead of intersection) of the fonts' glyph sets."
    )
    parser.add_argument(
        '-av', '--adjust-viewbox',
        type=bool,
        default=True,
        dest='adjust_view_box_to_glyph',
        help="vertically center the viewBox on the bounding box of all glyphs."
    )
    # parser.add_argument(
    #     'input_paths',
    #     metavar='FONT',
    #     nargs='+',
    #     help='OTF/TTF/WOFF/WOFF2 font file.',
    # )
    # parser.add_argument(
    #     '-i',
    #     type=bool,
    #     default="./font_path",
    #     help='OTF/TTF/WOFF/WOFF2 font file.',
    # )
    options = parser.parse_args(args)

    options.font_paths_list = validate_font_paths("./font_path") #等于字体文件夹图片
    return options



def mainInMemory(args: list = None) -> dict:
    """
    Converting ttf, otf, woff or woff2 to list of svg

    Parameters:
        args (list): list of parameters, ['-c', '000000', 'font.ttf'] by default
    Returns:
        list of svg strings
    """
    if args is None:
        args = ['-c', '000000', 'font.TTF']
    opts = get_options(args)

    if not opts.font_paths_list:
        raise Exception('Font paths needed')

    font_paths_list = opts.font_paths_list
    hex_colors_list = opts.colors_list #字体他

    # Confirm that the number of colors is the same as the fonts. If it's not,
    # extend the list of colors using SVG's default color (black), or trim the
    # list of colors.
    length_hex_colors = len(hex_colors_list)
    length_font_paths = len(font_paths_list)

    if length_hex_colors < length_font_paths:
        num_add_col = length_font_paths - length_hex_colors
        print("WARNING: The list of colors was extended with {} #000000 "
              "value(s).".format(num_add_col), file=sys.stderr)
        hex_colors_list.extend(['000000'] * num_add_col)

    elif length_hex_colors > length_font_paths:
        num_xtr_col = length_hex_colors - length_font_paths
        print("WARNING: The list of colors got the last {} value(s) truncated:"
              " {}".format(num_xtr_col, ' '.join(
            hex_colors_list[-num_xtr_col:])), file=sys.stderr)
        del hex_colors_list[length_font_paths:]

    output_folder_path = get_output_folder_path(opts.output_folder_path,
                                                font_paths_list[0])

    return processFontsInMemory(font_paths_list, hex_colors_list, output_folder_path,
                        opts)


def main(args=None):
    opts = get_options(args) #获得超参

    if not opts.font_paths_list:#没有
        return 1

    font_paths_list = opts.font_paths_list #输出文件夹
    hex_colors_list = opts.colors_list#颜色列表是00000

    # Confirm that the number of colors is the same as the fonts. If it's not,
    # extend the list of colors using SVG's default color (black), or trim the
    # list of colors.
    length_hex_colors = len(hex_colors_list) 
    length_font_paths = len(font_paths_list) 

    if length_hex_colors < length_font_paths:
        num_add_col = length_font_paths - length_hex_colors #计算差值
        print("WARNING: The list of colors was extended with {} #000000 "
              "value(s).".format(num_add_col), file=sys.stderr)
        hex_colors_list.extend(['000000'] * num_add_col) #乘倍数，扩展列表

    elif length_hex_colors > length_font_paths:
        num_xtr_col = length_hex_colors - length_font_paths
        print("WARNING: The list of colors got the last {} value(s) truncated:"
              " {}".format(num_xtr_col, ' '.join(
                  hex_colors_list[-num_xtr_col:])), file=sys.stderr)
        del hex_colors_list[length_font_paths:] #删除多余的颜色值

    output_folder_path = get_output_folder_path(opts.output_folder_path,
                                                font_paths_list[0]) #得到输出文件夹，和第一个处理的ttf，验证有没有这个文件夹

    return processFonts(font_paths_list, hex_colors_list, output_folder_path,
                       opts)#处理字体


if __name__ == "__main__":
    sys.exit(main())
    # sys.exit(mainInMemory())