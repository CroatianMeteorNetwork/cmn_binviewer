# coding=utf-8
# Copyright 2024- Mark McIntyre

from __future__ import print_function
import os
import sys
import platform
import shutil
import subprocess
import time
import errno
import logging
from FF_bin_suite import readFF, buildFF, add_text, saveImage
if sys.version_info[0] < 3:
    import tkMessageBox
else:
    import tkinter.messagebox as tkMessageBox


log = logging.getLogger("CMN_binViewer")


def makeMP4(FF_input, start_frame, end_frame, ff_dir, mp4_name='', deinterlace=True, annotate='', fps=25, FF_next=None, end_next=None, data_type=1,
            ffmpeg_path=''):
    if platform.system() == 'Windows':
        if ffmpeg_path == '':
            # ffmpeg.exe path
            root = os.path.dirname(__file__)
            ffmpeg_path = os.path.join(root, 'ffmpeg.exe')
            if not os.path.isfile(ffmpeg_path):
                ffmpeg_path = os.path.join(root, '..','RMS','Utils','ffmpeg.exe')
                if not os.path.isfile(ffmpeg_path):
                    tkMessageBox.showinfo("Alert", "ffmpeg.exe not found! Add its location to the config file")
                    return False
        if not os.path.isfile(ffmpeg_path.replace('"','')):
            tkMessageBox.showinfo("Alert", "ffmpeg.exe not found! Add its location to the config file")
            return False
    
    out_dir = os.path.split(mp4_name)[0]
    tmp_dir = out_dir + '/tmp_img_dir'
    if os.path.isdir(tmp_dir):
        shutil.rmtree(tmp_dir)
    mkdir_safe(tmp_dir)
    
    log.info('making mp4')

    cwd = os.getcwd()
    os.chdir(ff_dir)
    ffBinRead = readFF(FF_input, datatype=data_type)    
    for k in range(start_frame, end_frame+1):
        img_array = buildFF(ffBinRead, k, videoFlag = True)
        if annotate != '':
            img_array = add_text(img_array, annotate)
        _ = saveFrame(img_array, k, tmp_dir, FF_input)

        print('.', end='')
    if FF_next:
        ffBinRead = readFF(FF_next, datatype=data_type)    
        for k in range(0, end_next+1):
            img_array = buildFF(ffBinRead, k, videoFlag = True)
            if annotate != '':
                img_array = add_text(img_array, annotate)
            _ = saveFrame(img_array, k+end_frame+1, tmp_dir, FF_input)
            print('.', end='')
    print(' ')
    tmp_img_patt = os.path.abspath(os.path.join(tmp_dir, FF_input+"_%03d.png"))
    # If running on Windows, use ffmpeg.exe
    if platform.system() == 'Windows':
        # Construct the ecommand for ffmpeg           
        com = ffmpeg_path + " -hide_banner -loglevel error -pix_fmt yuv420p  -y -f image2 -pattern_type sequence -start_number " + str(start_frame) + " -i " + tmp_img_patt +" " + mp4_name
    else:
        # If avconv is not found, try using ffmpeg
        software_name = "avconv"
        if os.system(software_name + " --help > /dev/null"):
            software_name = "ffmpeg"
            # Construct the ecommand for ffmpeg           
            com = software_name + " -hide_banner -loglevel error -pix_fmt yuv420p  -y -f image2 -pattern_type sequence -start_number " + str(start_frame) + " -i " + tmp_img_patt +" " + mp4_name
        else:
            com = "cd " + tmp_dir + ";" \
                + software_name + " -v quiet -r 30 -y -start_number " + str(start_frame) + " -i " + tmp_img_patt \
                + " -vcodec libx264 -pix_fmt yuv420p -crf 25 -movflags faststart -g 15 -vf \"hqdn3d=4:3:6:4.5,lutyuv=y=gammaval(0.97)\" " \
                + mp4_name

    log.info(com)
    subprocess.call(com, shell=True, cwd=out_dir)
    
    #Delete temporary directory and files inside
    #print(tmp_dir)
    if os.path.isdir(tmp_dir):
        #print('deleting tempdir')
        try:
            shutil.rmtree(tmp_dir)
        except:
            # may occasionally fail due to ffmpeg thread still terminating
            # so catch this and wait a bit
            time.sleep(2)
            shutil.rmtree(tmp_dir)
    log.info('done')
    os.chdir(cwd)
    return True


def saveFrame(frame, frame_no, out_dir, file_name):
    file_name_saving = file_name + '_{:03d}'.format(frame_no) + '.png'
    out_path = os.path.join(out_dir, file_name_saving)
    saveImage(frame, out_path, False)
    return file_name_saving


def mkdir_safe(path):
    """ Makes a directory and handles all errors.
    """
    try:
        os.makedirs(path)
    except OSError as exc:
        if exc.errno == errno.EEXIST:
            pass
        else: 
            raise
