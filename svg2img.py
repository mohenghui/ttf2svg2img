import svglib
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPDF, renderPM
import os
# drawing = svg2rlg("save_svg/FZAiSJW/b.svg")
#renderPDF.drawToFile(drawing, "drawing.pdf")
def get_files(file_path,save_dir):
    for filepath,dirnames,filenames in os.walk(file_path):
        for filename in filenames:
            drawing=svg2rlg(os.path.join(filepath,filename))
            save_path=save_dir+'/'+filepath.split('/')[1]
            if not  os.path.exists(save_path):
                os.makedirs(save_path)
            # print((save_path,filename.split('.')[0]+".PNG"))
            renderPM.drawToFile(drawing,os.path.join(save_path,filename.split('.')[0]+".PNG"), fmt="PNG")
#renderPM.drawToFile(drawing, "drawing.jpg", fmt="JPG")

get_files('save_svg','save_img')