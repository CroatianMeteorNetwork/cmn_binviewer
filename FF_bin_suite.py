# coding=utf-8
# Copyright 2014 Denis Vida, denis.vida@gmail.com

# The FF_bin_suite is free software; you can redistribute
# it and/or modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation, version 2.

# The FF_bin_suite is distributed in the hope that it will be
# useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with the FF_bin_suite ; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA

"""Module for handling FF*.bin files produced by CAMS software.
Author: Denis Vida

Reading from FF*.bin files based on Matlab scripts by Peter S. Gural.
"""



import os
import subprocess
import platform
import six

import numpy as np
import logging
import astropy.io.fits as pyfits

from PIL import Image as img
from PIL import ImageFont
from PIL import ImageDraw
import imageio


gifsicle_name = "gifsicle.exe" #gifsicle.exe program name
font_name = "COUR.TTF"

run_dir = os.path.abspath(".")

log = logging.getLogger("CMN_binViewer")


class ff_struct:
    """ Default structure for a FF*.bin file.
    """
    def __init__(self):
        
        # Number of image rows
        self.nrows = 0

        # Number of image columns
        self.ncols = 0

        # 2*nbits compressed frames (OLD format)
        self.nbits = 0

        # Number of compressed frames (NEW format)
        self.nframes = 0

        # First frame number
        self.first = 0

        # Camera number (station ID) (OLD format)
        self.camno = 0

        # Decimation factor (NEW format)
        self.decimation_fact = 0

        # Interleave flag (0=prog, 1=even/odd, 2=odd/even) (NEW format)
        self.interleave_flag = 0

        # Frames per seconds (NEW format)
        self.fps = 0


        self.maxpixel = 0
        self.maxframe = 0
        self.avepixel = 0
        self.stdpixel = 0


def truth_generator():
    """ Generates True/False intermittently by calling:

    gen = truth_generator() 
    next(gen) #True
    next(gen) #False
    next(gen) #True
    ...
     """
    while 1:
        yield True
        yield False



def readFF(filename, datatype = 1):
    """Function for reading FF bin files.

    Returns a structure that allows access to individual parameters of the image
    e.g. print(readFF("FF300_20140802_205545_600_0090624.bin").nrows) to print out the number of rows
    e.g. print(readFF("FF300_20140802_205545_600_0090624.bin").maxpixel) to print out the array of nrows*ncols numbers which represent the image
    INPUTS:
        filename: file name from the file to be read
        datatype: type of data to be read, 1 for CAMS, 2 for Skypatrol
    """

    # Return Skypatrol BMP if datatype is set for Skypatrol
    if datatype == 2: 
        return readSkypatrolBMP(filename)

    # Return RMS fits format
    elif datatype == 3:
        return readFits(filename)

    fid = open(filename, 'rb')
    ff = ff_struct()

    # Check if it is the new of the old CAMS data format
    version_flag = int(np.fromfile(fid, dtype=np.int32, count = 1))

    # Old format
    if version_flag > 0:

        ff.nrows = version_flag
        ff.ncols = int(np.fromfile(fid, dtype=np.uint32, count = 1))
        ff.nbits = int(np.fromfile(fid, dtype=np.uint32, count = 1))
        ff.nframes = 2**ff.nbits
        ff.first = int(np.fromfile(fid, dtype=np.uint32, count = 1))
        ff.camno = int(np.fromfile(fid, dtype=np.uint32, count = 1))

        ff.decimation_fact = 1

        

    # New format
    elif version_flag == -1:

        ff.nrows = int(np.fromfile(fid, dtype=np.uint32, count = 1))
        ff.ncols = int(np.fromfile(fid, dtype=np.uint32, count = 1))

        ff.nframes = int(np.fromfile(fid, dtype=np.uint32, count = 1))
        ff.first = int(np.fromfile(fid, dtype=np.uint32, count = 1))
        ff.camno = int(np.fromfile(fid, dtype=np.uint32, count = 1))

        ff.decimation_fact = int(np.fromfile(fid, dtype=np.uint32, count = 1))

        ff.interleave_flag = int(np.fromfile(fid, dtype=np.uint32, count = 1))

        ff.fps = float(np.fromfile(fid, dtype=np.uint32, count = 1))/1000


    # Number of pixels in each image
    N = ff.nrows*ff.ncols

    # Try reading image arrays
    try:
        ff.maxpixel = np.reshape(np.fromfile(fid, dtype=np.uint8, count = N), (ff.nrows, ff.ncols))
        ff.maxframe = np.reshape(np.fromfile(fid, dtype=np.uint8, count = N), (ff.nrows, ff.ncols))
        ff.avepixel = np.reshape(np.fromfile(fid, dtype=np.uint8, count = N), (ff.nrows, ff.ncols))
        ff.stdpixel = np.reshape(np.fromfile(fid, dtype=np.uint8, count = N), (ff.nrows, ff.ncols))

    # If there is an error in reading, initialize empty arrays
    # The maxpixel image will contain random numbers, to show there was an error while loading
    except ValueError:
        ff.maxpixel = add_text(np.zeros((ff.nrows, ff.ncols), dtype=np.uint8), 'IMAGE LOADING ERROR')
        ff.maxframe = np.zeros((ff.nrows, ff.ncols), dtype=np.uint8)
        ff.avepixel = np.zeros((ff.nrows, ff.ncols), dtype=np.uint8)
        ff.stdpixel = np.zeros((ff.nrows, ff.ncols), dtype=np.uint8)



    # Used for video brightening, when video is darker than maxpixel
    ff.adjustment_scalar = np.mean(ff.maxpixel) / np.mean(ff.avepixel)

    return ff



def readSkypatrolBMP(img_name):
    """ Reads Skypatrol BMP and returns maxpixel and maxframe image array.

    INPUTS:
        img_name: path to Skypatrol BMP image
    OUTPUTS:
        ff: structure that holds information about the image, see ff_struct class"""

    bmp_data = img.open(img_name) #Open image
    bmp_array = np.asarray(bmp_data, dtype=np.uint8) #Convert to ndarray format

    bmp_array = np.dsplit(bmp_array, 3) #Split channels

    red_channel = np.clip(bmp_array[0], 0, 99) #Get red channel, clip values to 0-99 (low-byte)
    green_channel = np.clip(bmp_array[1].astype(np.uint16), 0, 255) #Get green channel, clip values to 0-255 (hi-byte)
    blue_channel = np.clip(bmp_array[2].astype(np.uint16), 0, 255) #Get blue channel, clip values to  0-255 (maxpixel image)

    nrows = len(blue_channel)
    ncols = len(blue_channel[0])


    max_pixel = np.reshape(blue_channel, (nrows, ncols)) #Maxpixel is stored in blue channel

    max_frame = np.reshape(red_channel+100*green_channel, (nrows, ncols)) #Maxframe in low-byte + 100 * hi-byte

    #Put data to FF array structure
    ff = ff_struct()
    ff.nrows = nrows
    ff.ncols = ncols
    ff.maxpixel = np.uint8(max_pixel)
    ff.maxframe = max_frame
    ff.avepixel = np.zeros(shape=(nrows, ncols), dtype=np.uint8)

    ff.adjustment_scalar = 1

    return ff



def readFits(filename):
    """ Read a FF structure from a FITS file. 
    
    Arguments:
        filename: [str] Name of FF*.fits file (either with FF and extension or without)
    
    Return:
        [ff structure]

    """

    # Init an empty FF structure
    ff = ff_struct()

    fid = open(filename, "rb")

    # Read in the FITS
    hdulist = pyfits.open(fid)

    # Read the header
    head = hdulist[0].header

    # Read in the data from the header
    ff.nrows = head['NROWS']
    ff.ncols = head['NCOLS']
    ff.nbits = head['NBITS']
    ff.nframes = head['NFRAMES']
    ff.first = head['FIRST']
    ff.camno = head['CAMNO']
    ff.fps = head['FPS']

    # Read in the image data
    ff.maxpixel = hdulist[1].data
    ff.maxframe = hdulist[2].data
    ff.avepixel = hdulist[3].data
    ff.stdpixel = hdulist[4].data

    # CLose the FITS file
    hdulist.close()

    # Used for video brightening, when video is darker than maxpixel
    ff.adjustment_scalar = np.mean(ff.maxpixel) / np.mean(ff.avepixel)

    return ff



def buildFF(ff, kframe, videoFlag=False, no_background=False):
    """Function for returning the K frame from a FF bin file, and makes brightness corrections if videoFlag variable is set to True.

    Returns an array of nrows * ncols that represents the k-frame image
    e.g. buildFF(readFF("FF300_20140802_205545_600_0090624.bin"), 100) returns the 100th frame (range 0 - 255)"""

    if no_background:
        # No avepixel as background
        img = np.zeros_like(ff.avepixel)
    else:
        if videoFlag:
            img = np.copy(ff.avepixel)
        else:
            # When videoFlag is False, every consecutive frame will be added to the average pixel, producing a stacking effect
            img = ff.avepixel

    k = np.where(ff.maxframe == kframe)

    img[k] = ff.maxpixel[k]

    if videoFlag and (ff.adjustment_scalar > 2):
        img = img * ff.adjustment_scalar*1.2 + 10
        img = np.clip(img, 0, 255)

    return img



def add_text(ff_array, img_text):
    """ Adds text to numpy array image.
    """
    im = img.fromarray(np.uint8(ff_array))

    im = im.convert('RGB')
    draw = ImageDraw.Draw(im)

    # Try to load a specefic font, if it is not available, load a default one
    try:
        font = ImageFont.truetype(font_name, 14)

    except:
        font = ImageFont.load_default()

    # Draw the text on the image, in the upper left corent
    draw.text((0, 0), img_text, (255,255,0), font=font)
    draw = ImageDraw.Draw(im)

    # Convert the type of the image to grayscale, with one color
    try:
        if len(ff_array[0][0]) != 3:
            im = im.convert('L')
    except:
        im = im.convert('L')

    return np.array(im)



def saveImage(ff_array, img_name, print_name=True, bmp_24bit=False, extra_text=None):
    """ Save image (choose format by writing extension, e.g. *.jpg or *.bmp) from numpy array with name on it if print_name is True (default).

    ff_array: numpy array, e.g. ff_array = buildFF(readFF("FF300_20140802_205545_600_0090624.bin"), 250)
    img_name: name of JPG image to be saved
    print_name: if image name is to be embeded into image_list
    bmp_24bit: if image is to be saved as 24 bit BMP (RGB)

    usage: saveImage(buildFF(readFF("FF300_20140802_205545_600_0090624.bin"), 250), 'test.jpg')
    """
    if print_name is True:
        text_to_add = os.path.basename(img_name) + extra_text
        ff_array = add_text(ff_array, text_to_add)

    im = img.fromarray(np.uint8(ff_array))

    try:
        if len(ff_array[0][0]) != 3:
            im = im.convert('L')
    except:
        im = im.convert('L')

    if bmp_24bit:
        im = im.convert('RGB')

    im.save(img_name)



def deinterlace_array_odd(ff_image):
    """ Deinterlaces the numpy array image by duplicating the odd frame. 
    """
    truth_gen = truth_generator()
    deinterlaced_image = np.copy(ff_image) #deepcopy ff_image to new array
    old_row = ff_image[0]
    for row_num in range(len(ff_image)):
        if next(truth_gen) is True:
            deinterlaced_image[row_num] = np.copy(ff_image[row_num])
            old_row = ff_image[row_num]
        else:
            deinterlaced_image[row_num] = np.copy(old_row)

    deinterlaced_image = move_array_1up(deinterlaced_image)

    return deinterlaced_image



def deinterlace_array_even(ff_image):
    """ Deinterlaces the numpy array image by duplicating the even frame. 
    """
    truth_gen = truth_generator()
    deinterlaced_image = np.copy(ff_image) #deepcopy ff_image to new array
    old_row = ff_image[-1]
    for row_num in reversed(range(len(ff_image))):
        if next(truth_gen) is True:
            deinterlaced_image[row_num] = np.copy(ff_image[row_num])
            old_row = ff_image[row_num]
        else:
            deinterlaced_image[row_num] = np.copy(old_row)

    return deinterlaced_image



def blend_lighten(arr1, arr2):
    """ Blends two image array with lighen method (only takes the lighter pixel on each spot).
    """
    arr1 = arr1.astype(np.int16)
    temp = arr1 - arr2 #Subtract two arrays
    temp[temp > 0] = 0 #Repace all >0 evements with 0
    new_arr = arr1 - temp
    new_arr = new_arr.astype(np.uint8)
    return new_arr #Return "greater than" values


def move_array_1up(array):
    """ Moves image array 1 pixel up, and fills the bottom with zeroes.
    """
    array = np.delete(array, (0), axis=0)
    array = np.vstack([array, np.zeros(len(array[0]), dtype = np.uint8)])

    return array



def deinterlace_blend(image_array):
    """ Deinterlaces the image by making an odd and even frame, then blends them by lighten method.
    """

    #image_odd_d = deinterlace_array_odd(image_array)
    image_odd_d = deinterlace_array_odd(image_array)
    image_even = deinterlace_array_even(image_array)
    full_proc_image = blend_lighten(image_odd_d, image_even)

    return full_proc_image


def makeGIF(FF_input, start_frame=0, end_frame =255, ff_dir = '.', deinterlace = True, print_name = True, 
            optimize = True, Flat_frame = None, Flat_frame_scalar = None, dark_frame = None, 
            gif_name_parse = None, repeat = True, fps = 25, minv = None, gamma = None, maxv = None, perfield = False, data_type=1):
    """ Makes a GIF animation for given FF_file, in given frame range (0-255).

    start_frame: Starting frame (default 0)
    end_frame: Last frame for gif animation (default 255)
    ff_dir: A directory in which FF*.bin files are can be given as ff_dir (default is the current directory)
    deinterlace: Deinterlacing by odd frame can be chosen (True by default)
    print_name: Printing File name on image and frame number can be chosen (True by default)
    optimize: Image optimizing can be chosen (reduces file size) (True by default)
    Flat_frame: flat frame array which can be applied to every frame (default None)
    Flat_frame_scalar: a scalar value of flat frame mean which is appled only in case when flat frame is used. steps up levels on image by this value (default None)
    dark_frame: dark frame to be subtracted from each frame of animation
    gif_name_parse: define a special GIF name
    repeat: repeat GIF in loops (default: True)
    fps: frames per second (default: 25)
    minv: levels adjustment minimum level (default None)
    gamma: levels adjustment gamma (default None)
    maxv: levels adjustment maximum level (default None)
    perfield: if True, every frame will be split into an odd and even field (x2 more frames) (default False)
    data_type: 1 CAMS, 2 skypatrol,, 3 RMS
    """

    os.chdir(ff_dir)

    images = []

    # Check if FF_file is just one of a list of files with start - end frames.
    # six.string_types includes both str and unicode types. 
    if isinstance(FF_input, six.string_types): 
        ff_list = [[FF_input, (start_frame, end_frame)]]
        gif_name = FF_input.split('.')[0] + "fr_" + str(start_frame) + "-" + str(end_frame) + ".gif"
        FF_input = ff_list
    else:
        gif_name = ff_dir + "_".join(FF_input[0][0].split('.')[0].split("_")[0:2]) + "_all-night.gif"
    
    for entry in FF_input:
        FF_file = entry[0]
        start_frame = entry[1][0]
        end_frame = entry[1][1]

        if (end_frame>start_frame) and (start_frame>=0) and (end_frame<=255):
            pass
        else:
            raise ValueError("Incorrect input parameters! Start frame must be before end frame and both must be withnin bounds [0, 255]")

        # Read FF bin
        ffBinRead = readFF(FF_file, datatype=data_type)
        
        for k in range(start_frame, end_frame+1):
            img_array = buildFF(ffBinRead, k, videoFlag = True)

            if perfield is True: #Disable deinterlace when "perfield" is on
                deinterlace = False

            img_array = process_array(img_array, Flat_frame, Flat_frame_scalar, dark_frame, deinterlace) #Calibrate individual frames

            img_array = adjust_levels(img_array, minv, gamma, maxv) #Adjust levels on individual frames

            # Every frame will be split into an odd and even field (x2 more frames)
            FF_file = FF_file.split(os.sep)[-1]
            if perfield is True: 
                odd_array = deinterlace_array_odd(img_array)
                even_array = deinterlace_array_even(img_array)

                # Add name
                if print_name is True:
                    odd_text = FF_file+" frame = "+str(k).zfill(3)+'.5'
                    even_text = FF_file+" frame = "+str(k).zfill(3)+'.0'
                    odd_array = add_text(odd_array, odd_text)
                    even_array = add_text(even_array, even_text)

                images.append(np.uint8(odd_array))
                images.append(np.uint8(even_array))

                continue

            # Add name
            if print_name is True:
                img_text = FF_file+" frame = "+str(k).zfill(3)
                img_array = add_text(img_array, img_text)

            images.append(np.uint8(img_array))


    # ##TEST SAVE JPGs
    # c = 0
    # for k in images:
    #   saveImage(k, str(c)+".jpg")
    #   c +=1

    log.info('Making gif...')
    #Write GIF file
    if gif_name_parse is not None:
        gif_name = gif_name_parse

    # Write the gif to disk
    imageio.mimsave(gif_name, images, duration=1/float(fps), loop=int(not repeat), subrectangles=True)
    
    # Optimize gif only under windows
    if optimize and (platform.system() == 'Windows'):
        log.info(' Optimizing...')
        old_dir = os.getcwd()
        os.chdir(run_dir)
        args = ['-O3', '--use-colormap', 'grey', '--colors', '256', gif_name, '-o', gif_name]
        #print(args)
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        subprocess.Popen([gifsicle_name] + args, startupinfo=startupinfo).wait()
        os.chdir(old_dir)
    
    log.info('Done!')

    os.chdir(run_dir)

    return True



def get_FTPdetect_frames(FTPdetect_file, minimum_frames):
    """ Returns a list of FF*.bin files with coresponding frames for a detected meteor in format [["FF*bin", (start_frame, end_frame)]]
    """

    def get_frames(frame_list):
        if len(frame_list)<minimum_frames*2: #Times 2 because len(frames) actually contains every half-frame also
            ff_bin_list.pop()
            return None
        min_frame = int(float(frame_list[0]))
        max_frame = int(float(frame_list[-1]))
        ff_bin_list[-1].append((min_frame, max_frame))

        #print(len(frame_list))
    
    if not os.path.isfile(FTPdetect_file):
        return False

    FTPdetect_file_content = open(FTPdetect_file).readlines()

    if int(FTPdetect_file_content[0].split('=')[1]) == 0: #Solving issue when no meteors are in the file
        return []

    ff_bin_list = []

    skip = 0
    frame_list = []
    for line in FTPdetect_file_content[12:]:
        #print(line)

        if ("-------------------------------------------------------" in line):
            get_frames(frame_list)
            

        if skip>0:
            skip -= 1
            continue

        line = line.replace('\n', '')

        if ("FF" in line) and (".bin" in line):
            ff_bin_list.append([line.strip()])
            skip = 2
            del frame_list
            frame_list = []
            continue
        
        frame_list.append(line.split()[0])

    get_frames(frame_list) #Writing the last FF bin file frames in a list

    return ff_bin_list



def make_night_GIF(night_dir, minimum_frames = 10):
    """Makes a GIF of events during the whole night. The minimum number of frames for event to pass the treshold filter is given in minimum_frames variable (10 is default).

    Usage:
    e.g. make_night_GIF("C:\\Users\\Laptop\\Desktop\\2014080809-Processed")
    """

    if not night_dir[-1] == os.sep:
        night_dir += os.sep

    if not os.path.exists(night_dir):
        log.info("Folder "+night_dir+" not found!")
        return False

    FTPdetect_file = ""
    for line in os.listdir(night_dir):
        if ("FTPdetectinfo_" in line) and (".txt" in line) and ("_original" not in line):
            FTPdetect_file = line
            break

    #print(get_FTPdetect_frames(FTPdetect_file, minimum_frames))

    old_dir = os.getcwd()
    os.chdir(night_dir)

    if FTPdetect_file != "":
        log.info('Processing folder: '+night_dir)
        makeGIF(get_FTPdetect_frames(FTPdetect_file, minimum_frames), ff_dir = night_dir)
    else:
        log.info("FTPdetectinfo file in "+night_dir+" not found!")
        return False

    os.chdir(old_dir)

    return True



def fixFlat_frame(Flat_frame, Flat_frame_scalar):
    """ Makes a Flat_frame image by calculating Flat_frame value of every column, to prevent spots on the image.
    """
    
    nrows = len(Flat_frame)
    ncols = len(Flat_frame[0])

    col_Flat_frame = []
    for j in range(ncols):
        col_sum=[]
        for i in range(nrows):
            temp_lvl = Flat_frame[i][j]
            if temp_lvl < Flat_frame_scalar*10:
                col_sum.append(temp_lvl)
        col_Flat_frame.append(np.median(col_sum))

    return np.reshape(len(Flat_frame)*col_Flat_frame, (len(Flat_frame), len(Flat_frame[0])))



def add_scalar(array, scalar, min_clip = 0, max_clip = 255):
    """ Function that add a scalar value to all 2D array elements, with respect to minumum and maximum values.
    """

    #Clip values
    return np.clip(array + scalar, min_clip, max_clip) 
    


def max_nomean(ff_bin, Flat_frame = None, Flat_frame_scalar = None):
    """ Returns an array which represents maxpixel image with removed flat field and mean background, so just detections are visible.
    """

    img_average = ff_bin.avepixel
    if Flat_frame is not None:
        img_average = np.subtract(img_average, Flat_frame) #Substract flat from average

    img_max = ff_bin.maxpixel
    if Flat_frame is not None:
        img_max = np.subtract(img_max, Flat_frame) #Flat field correction of maxpixel image

    img_max_noavg = deinterlace_blend(np.subtract(img_max, img_average))

    return img_max_noavg



def process_array(img_array, Flat_frame = None, Flat_frame_scalar = None, dark_frame = None, deinterlace = False, field = 0):
    """ Processes given array with given frames. Used in CMN_binViewer.
    """

    if dark_frame is not None:
        img_array = np.subtract(img_array, dark_frame)

    if Flat_frame is not None:
        img_array = img_array.astype(float)

        Flat_frame[Flat_frame == 0] = 1
        img_array = img_array / Flat_frame.astype(float)
        img_array = np.multiply(img_array, Flat_frame_scalar)

    if (dark_frame is not None) or (Flat_frame is not None):
        img_array = np.clip(img_array, 0, 255)

    img_array = img_array.astype(np.uint8)

    if field == 1:  #Odd field
        img_array = deinterlace_array_odd(img_array)
    elif field == 2:  #Even field
        img_array = deinterlace_array_even(img_array)

    if deinterlace is True:
        img_array = deinterlace_blend(img_array)


    return img_array


def get_processed_frames(ff_bin, save_path = '.', data_type=1, Flat_frame=None, Flat_frame_scalar=None, dark_frame=None, start_frame=0, end_frame=255, logsort_export=False, no_background=False):
    """ Makes calibrated BMPs of a particular detection. Used for fireball processing.

    ff_bin: *.bin file (or Skypatrol BMP) name and path
    save_path: path where to save processed frames
    data_type: 1 for CAMS (default), 2 for Skypatrol, 3 RMS
    Flat_frame: flat frame array (load flat frame or make it)
    Flat_frame_scalar: flat frame median value (load flat frame or make it)
    dark_frame: dark frame array
    start_frame: first frame to be taken
    end_frame: last frame to be taken
    logsort_export: images will be exported as 24 bit BMPs instead of 8 bit if True
    no_background: images will be exported without background if True
    """

    # Make stack of frames on Skypatrol data
    if data_type == 2:
        array = readFF(ff_bin, data_type).maxpixel
        nrows = len(array)
        ncols = len(array[0])
        skypatrol_stacked_image = np.zeros(shape=(nrows, ncols), dtype=int)

    # Read FF bin
    ffBinRead = readFF(ff_bin, data_type)

    image_list = []

    for nframe in range(start_frame, end_frame+1):

        frame_img = buildFF(ffBinRead, nframe, videoFlag = True, no_background = no_background) #Get individual frames

        # Calibrate individual frame
        frame_img = process_array(frame_img, Flat_frame, Flat_frame_scalar, dark_frame)

        ff_bin_name = ff_bin.split(os.sep)[-1]
        #if logsort_export:
        #    img_name_prefix = str(nframe).zfill(4)
        #else:
        img_name_prefix = ff_bin_name.split('.')[0]+"_frame_"+str(nframe).zfill(4)

        img_path_prefix = os.path.join(save_path, img_name_prefix)

        # CAMS data type
        if (data_type == 1) or (data_type == 3):
            odd_frame_img = deinterlace_array_odd(frame_img)
            saveImage(odd_frame_img, img_path_prefix+"_0dd.bmp", print_name = False, bmp_24bit = logsort_export)
            image_list.append(img_name_prefix+"_0dd.bmp")

            even_frame_img = deinterlace_array_even(frame_img)
            saveImage(even_frame_img, img_path_prefix+"_Even.bmp", print_name = False, bmp_24bit = logsort_export)
            image_list.append(img_name_prefix+"_Even.bmp")

        else:
            #Skypatrol data type (reverse order or frames)

            odd_frame_img = deinterlace_array_odd(frame_img)
            saveImage(odd_frame_img, img_path_prefix+"_Even.bmp", print_name = False, bmp_24bit = logsort_export)
            image_list.append(img_name_prefix+"_Even.bmp")

            skypatrol_stacked_image = blend_lighten(skypatrol_stacked_image, odd_frame_img)

            even_frame_img = deinterlace_array_even(frame_img)
            saveImage(even_frame_img, img_path_prefix+"_Odd.bmp", print_name = False, bmp_24bit = logsort_export)
            image_list.append(img_name_prefix+"_Odd.bmp")

            skypatrol_stacked_image = np.subtract(skypatrol_stacked_image, even_frame_img)
            skypatrol_stacked_image = np.clip(skypatrol_stacked_image, 0, 255)

    # Make stack of frames on Skypatrol data
    if data_type == 2:
        saveImage(skypatrol_stacked_image, os.path.join(save_path, ff_bin_name+'_stacked.bmp'), print_name = False, bmp_24bit = logsort_export)

    return image_list

            

def get_detection_only(ff_content, start_frame = 0, end_frame = 255, Flat_frame = None, Flat_frame_scalar = None, dark_frame = None, deinterlace = False):
    """ Return an array which contains only the detection frames, lighten blended.

    ff_content: ff file structure
    start_frame: default 0
    end_frame: default 255
    Flat_frame: flat frame array (load flat frame or make it) (default None)
    Flat_frame_scalar: flat frame median value (load flat frame or make it) (defualt None)
    dark_frame: dark frame (default None)
    """
    
    for nframe in range(start_frame, end_frame+1):
        frame_img = buildFF(ff_content, nframe) #Get individual frames

    if ff_content.adjustment_scalar > 2:
        frame_img = frame_img * ff_content.adjustment_scalar
        frame_img = np.clip(frame_img, 0, 255)

    frame_img = process_array(frame_img, Flat_frame, Flat_frame_scalar, dark_frame, deinterlace)
        
    return frame_img



@np.vectorize
def blend_darken(a, b):
    """ Helper function for darken blending.
    """
    if a>b:
        return b
    return a



@np.vectorize
def blend_average(*args):
    """ Blends images by averaging pixels.
    """
    s = 0
    for i in args:
        s+=i
    return s/len(args)



@np.vectorize
def blend_median(*args):
    """ Blends images by taking the median of each pixel.
    """
    sort = sorted(args)
    sort_len = len(sort)

    if sort_len == 1:
        return sort[0]

    elif sort_len == 2:
        return (sort[0] + sort[1])/2

    middle = int(sort_len/2)
    
    return sort[middle]



def chop_flat_processes(img_num, step = 31):
    """ Gives a tuple of ranges to chop the flat field arrays if there are more than 32 of them. For img_num = 70, it would return [(0, 32), (32, 64), (64, 70)]
    """
    ranges_list = []
    old = 0
    for i in range(step, img_num, step):
        ranges_list.append((old, i))
        old = i
    ranges_list.append((old, img_num))
    return ranges_list



def make_flat_frame(flat_dir, flat_save = 'flat.bmp', col_corrected = False, dark_frame = None, data_type=1):
    """ Return a flat frame array and flat frame median value. Makes a flat frame by comparing given images and taking the minimum value on a given position of all images.

    flat_dir: directory where FF*.bin files are held
    flat_save: name of file to be saved, dave directory is flat_dir (default: flat.bmp)
    dark_frame: array which contains dark frame (None by default, then it is read from the folder, if it exists)
    data_type: 1 CAMS, 2 skypatrol, 3 RMS
    Lines can be vertically averaged by col_corrected = True (default)"""

    # I assume CAMS creates FF.bin files, but RMS creates FF.fits ones
    filetype = 'bin'
    if data_type == 3:
        filetype = 'fits'

    flat_raw = [os.path.join(flat_dir, line) for line in os.listdir(flat_dir) if ('FF' in line) and (line.split('.')[-1] == filetype)]
    flat_arrays = []
    try:
        first_raw = flat_raw[0]
    except:
        return False

    ff = readFF(first_raw, datatype=data_type)
    nrows = ff.nrows
    ncols = ff.ncols

    #log.info('Making flat frame...')
    #log.info(f'Flat frame resolution: {nrows} {ncols}')

    # Try loading dark frame, if not given
    if dark_frame is None:
        
        try:
            dark_frame = load_dark(flat_dir + 'dark.bmp')

        except:
            dark_frame = np.zeros(shape=(nrows, ncols), dtype=int) 

    elif isinstance(dark_frame, bool):
        dark_frame = np.zeros(shape=(nrows, ncols), dtype=int) 

    for line in flat_raw:

        flat_temp = readFF(line, datatype=data_type).avepixel
        flat_temp = np.subtract(flat_temp, dark_frame)
        flat_temp = np.clip(flat_temp, 0, 255)

        flat_arrays.append(flat_temp)

    #Flat_frame = flat_arrays[0]

    #for flat_array in flat_arrays:
        #Flat_frame = blend_darken(Flat_frame, flat_array) #Darken flat
        #Flat_frame = blend_average(Flat_frame, flat_array) #Average flat
    
    #Handle the problem when there are more than 32 images (numpy's vectorize function can't recieve more than 32 arguments)
    if len(flat_arrays) > 32:
        temp_arrays = []
        for start, end in chop_flat_processes(len(flat_arrays)):
            temp_arrays.append(blend_median(*flat_arrays[start:end]))

        Flat_frame = blend_median(*temp_arrays)

    elif len(flat_arrays) > 1024:
        log.info('No more than 1024 images can be processed into a flat field!!!')
    else:
        Flat_frame = blend_median(*flat_arrays) #Median

    Flat_frame_scalar = int(np.median(Flat_frame)) #Calculate the median value of Flat_frame image to correct the final image

    if col_corrected is True:
        Flat_frame = fixFlat_frame(Flat_frame, Flat_frame_scalar) #Average each column in Flat_frame (expells hot pixels from Flat_frame)

    if os.sep not in flat_save:
        flat_save = os.path.join(flat_dir, flat_save)

    saveImage(Flat_frame, flat_save, print_name = False)
    #log.info('Done!')
    return Flat_frame, Flat_frame_scalar



def load_flat(flat_bmp = 'flat.bmp'):
    """ Loads a flat frame from BMP file into numpy array and calculates flat mean value.

    flat_bmp: name of BMP which contains the flat file (default: .\\flat.bmp)"""
    flat_img = img.open(flat_bmp)
    flat_img = flat_img.convert('L')
    flat_img.load()

    flat_array = np.asarray(flat_img, dtype=int)

    Flat_frame_scalar = int(np.median(flat_array))

    return flat_array, Flat_frame_scalar



def load_dark(dark_bmp = 'dark.bmp'):
    """ Loads a dark frame from BMP file into numpy array.

    dark_bmp: name of BMP which contains the dark file (default: .\\dark.bmp)"""

    dark_img = img.open(dark_bmp)
    dark_img = dark_img.convert('L')
    dark_img.load()

    dark_array = np.asarray(dark_img, dtype=int)

    return dark_array



def get_FTPdetect_coordinates(FTPdetect_file_content, ff_bin, meteor_no = 1):
    """ Returns a list of FF*.bin coordinates of a specific bin file and a meteor on that image as a list of tuples e.g. [(15, 20), (16, 21), (17, 22)] and the rotation angle of the meteor.
    """

    if int(FTPdetect_file_content[0].split('=')[1]) == 0: #Solving issue when no meteors are in the file
        return [], 0, 0

    skip = 0
    skip_to_end = False
    coord_list = []
    HT_rho = 0
    HT_phi = 0

    found_bin = False
    found_meteor = False
    read_angle = False

    for line in FTPdetect_file_content[12:]:

        if skip_to_end:
            if ("-------------------------------------------------------" in line):
                skip_to_end = False
                continue
            continue

        if skip>0:
            skip -= 1
            continue

        if ff_bin in line:
            found_bin = True
            skip = 1
            continue

        if found_bin and not found_meteor:
            line = line.split()
            if int(float(line[1])) == meteor_no:
                found_meteor = True
            else:
                skip_to_end = True

        if found_bin and found_meteor:
            if read_angle is False:
                HT_phi = float(line[-1])
                HT_rho = float(line[-2])
                read_angle = True
                continue

            if ("-------------------------------------------------------" in line):
                break

            line = line.split()
            coord_list.append((float(line[0]), int(round(float(line[1]), 0)), int(round(float(line[2]), 0))))

    return (coord_list, HT_rho, HT_phi)



def markDetections(image_array, detections_array, edge_marker=True, edge_thickness=2, edge_minimum=36):
    """ Takes an B/W 8-bit image and marks detections by pixel coordinates in detections_array. Returns a RGB array. 

    image_array: numpy array containing the image
    detections_array: list of detections (frame, x, y)
    edge_marker: marks the detection on the edge of an image if True with red
    edge_thickness: edge marker thickness in pixels
    edge_minimum: minimum edge width in pixels
    """

    def minimumEdge(var_min, var_max, img_var_size, edge_minimum):
        """ Check for minimum edge width. """
        if var_min > var_max:
            var_min, var_max = var_max, var_min

        if abs(var_max - var_min) < edge_minimum:
            var_diff = int((edge_minimum - abs(var_max - var_min)) /2)
            var_max += var_diff

            var_min -= var_diff

        if var_max >= img_var_size:
            var_max = img_var_size - 1

        if var_min < 0:
            var_min = 0

        return var_min, var_max


    redImage = np.copy(image_array)
    greenImage = np.copy(image_array)
    blueImage = np.copy(image_array)
    
    # Extract position of each point
    frames, y, x = zip(*detections_array)

    # Change each given point to green
    redImage[x, y] = 0
    greenImage[x, y] = 255
    blueImage[x, y] = 0

    if edge_marker:
        # Mark point range on the edge of the image

        img_x_size = len(image_array)
        img_y_size = len(image_array[0])

        # Find the range of edge pixels to draw
        x_min, x_max = minimumEdge(min(x), max(x)+1, img_x_size, edge_minimum)
        y_min, y_max = minimumEdge(min(y), max(y)+1, img_y_size, edge_minimum)

        x_range = list(range(x_min, x_max))
        y_range = list(range(y_min, y_max))

        x_edge = []
        y_edge = []

        for border_px in range(0, edge_thickness):
            x_edge += len(y_range) * [border_px] + x_range
            y_edge += y_range + len(x_range) * [border_px]

        redImage[x_edge, y_edge] = 255
        greenImage[x_edge, y_edge] = 0
        blueImage[x_edge, y_edge] = 0

        

    return np.dstack((redImage, greenImage, blueImage))



def find_crop_size(crop_array, size = 15):
    """ Goes thorugh rotated crop_array and finds values with 255. Marks the first and last position of those values and widens the crop coordinates by "size" in pixels.
    """
    nrows = len(crop_array)
    ncols = len(crop_array[0])
    first_coord = (0, 0)
    last_coord = (nrows, ncols)
    first_found = False

    for j in range(ncols):
        for i in range(nrows):
            if crop_array[i][j] == 255:
                if first_found is False:
                    first_coord = (i, j)
                    first_found = True
                    continue
                last_coord = (i, j)

    first_x = first_coord[1]
    first_y = first_coord[0]
    last_x = last_coord[1]
    last_y = last_coord[0]

    first_y = first_y-size
    if first_y<0:
        first_y = 0

    last_y = last_y+size
    if last_y>nrows:
        last_y = nrows

    return first_x, first_y, last_x, last_y


def get_lightcurve(meteor_array):
    """ Calculates the sum of column level values of a given array. For croped meteor image this gives its lightcurve.
    """
    ncols = len(meteor_array[0])

    lightcurve = []
    for i in range(ncols-1):
        lightcurve.append(np.sum(meteor_array[:, i:i+1]))

    return lightcurve


def colorize_maxframe(ff_bin, minv = None, gamma = None, maxv = None):
    """ Colorizes the B/W maxframe into red/blue image. Odd frames are colored red, even frames are colored blue.
    """

    ff_maxframe = ff_bin.maxpixel.astype(np.int16)
    ff_avgframe = ff_bin.avepixel.astype(np.int16)


    ff_maxframe_noavg = np.subtract(ff_maxframe, ff_avgframe)



    odd_frame = deinterlace_array_odd(ff_maxframe_noavg)
    even_frame = deinterlace_array_even(ff_maxframe_noavg)

    #Adjust levels (if any given)
    odd_frame = adjust_levels(odd_frame, minv, gamma, maxv)
    even_frame = adjust_levels(even_frame, minv, gamma, maxv)

    colored_array = np.dstack((odd_frame, even_frame, even_frame)) #R G B

    avg_rgb = np.dstack((ff_avgframe, ff_avgframe, ff_avgframe))
    colored_array = np.clip(np.add(colored_array, avg_rgb), 0, 255).astype(np.uint8)

    return colored_array



def adjust_levels(img_array, minv, gamma, maxv):
    """Adjusts levels on image with given parameters.

    img_array: input image array
    minv: minimum value of elements
    gamma: gamma value
    maxv: maximum value of elements
    """
    if (minv is None) and (gamma is None) and (maxv is None):
        return img_array #Return the same array if parameters are None

    minv= minv/255.0
    maxv= maxv/255.0
    _interval= maxv - minv
    _invgamma= 1.0/gamma

    img_array = img_array.astype(float)
    img_array = img_array / 255 #Reduce array to 0-1 values

    img_array = ((img_array - minv)/_interval)**_invgamma #Calculate new levels

    img_array = img_array * 255
    img_array = np.clip(img_array, 0, 255) #Convert back to 0-255 values
    img_array = img_array.astype(np.uint8)

    return img_array
    


def rescaleIntensity(image, in_range):
    """ Rescale the image with given intensity range. 

    @param image: [ndarray] 8-bit input image
    @param in_range: [tuple] a tuple of minimum and maximum values to rescale
    """

    imin, imax = in_range
    omin, omax = (0.0, 1.0)

    # Clip image values to the given range
    image = np.clip(image, imin, imax)

    # Rescale intensities
    image = (image - imin) / float(imax - imin)
    return image * (omax - omin) + omin



def cropDetectionSegments(ffBinRead, segmentList, cropSize = 64):
    """ Crops small images around detections.
    
    ffBinRead: read FF bin structure 
    segmentList: list of coordinate tuples [(x1, y1), (x2, y2),...]
    cropSize: image square size in pixels (e.g. 64x64 pixels)"""

    ncols = ffBinRead.ncols - 1
    nrows = ffBinRead.nrows - 1

    cropedList = []

    for coordinate in segmentList[0]:
        frame, x, y = coordinate

        x = int(round(x, 0))

        # Make sure each center row is even
        y = int(y)
        if y % 2 == 1:
            y += 1
        
        x_left = x - cropSize
        y_left = y - cropSize

        x_right = x + cropSize
        y_right = y + cropSize

        x_diff = 0
        y_diff = 0
        x_end = cropSize*2
        y_end = cropSize*2

        fillZeoresFlag = False
        if x_left < 0:
            fillZeoresFlag = True
            x_diff = -x_left
            x_end = cropSize*2

            x_left = 0
            

        if y_left < 0:
            fillZeoresFlag = True
            y_diff = -y_left
            y_end = cropSize*2

            y_left = 0
            

        if x_right > ncols:
            fillZeoresFlag = True
            x_diff = 0
            x_end = cropSize*2 - (x_right - ncols)

            x_right = ncols
            

        if y_right > nrows:
            fillZeoresFlag = True
            y_diff = 0
            y_end = cropSize*2 - (y_right - nrows - 1)

            y_right = nrows + 1
            

        imageArray = buildFF(ffBinRead, int(frame), videoFlag = True)

        # If croped area is in the corner, fill corner with zeroes
        if fillZeoresFlag:

            cropedArray = np.zeros(shape =(cropSize*2, cropSize*2))
            tempCrop = imageArray[y_left:y_right, x_left:x_right]

            cropedArray[y_diff:y_end, x_diff:x_end] = tempCrop
        
        else:
            cropedArray = imageArray[y_left:y_right, x_left:x_right]

        if frame % 1 == 0:
            # Deinterlace odd
            cropedArray = deinterlace_array_odd(cropedArray)
        else:
            # Deinterlace even
            cropedArray = deinterlace_array_even(cropedArray)

        cropedList.append(cropedArray)

        #saveImage(cropedArray, "test_"+str(frame)+'.bmp', print_name = False)

    return cropedList
        





# if __name__ == "__main__":

    # import matplotlib.pyplot as plt

    #ftpdetect = "C:\\Users\\Laptop\\Desktop\\2014080809-Processed\\FTPdetectinfo_0453_2014_08_08.txt"

    #makeGIF(get_FTPdetect_frames(ftpdetect), 'C:\\Users\\Laptop\\Desktop\\2014080809-Processed')

    #make_night_GIF("C:\\Users\\Laptop\\Desktop\\VIB_2014080809-Processed")
    #make_night_GIF("C:\\Users\\Laptop\\Desktop\\PUA_2014080809-Processed")
    #make_night_GIF("E:\\VSA2014\\KOWA_RAW\\2014_08_02_19_54_58_archived")


    #def batchmakeGIF(ff_list, deinterlace = True, optimize = True):
    #   for entry in ff_list:

    #image_name = "FF451_20140810_205811_500_0118528.bin"

    #image_k = buildFF(readFF(image_name), 70) #Show K-frame from image

    #saveImage(move_array_1up(deinterlace_array_odd(image_k)), 'test_odd.bmp')
    #saveImage(deinterlace_array_even(image_k), 'test_even.bmp')
    #saveImage(image_k, 'test_raw.bmp')


    #full_proc_image = deinterlace_blend(image_array)
    #saveImage(full_proc_image, 'test_full_proc.bmp')

    #image_ave = deinterlace_blend(readFF(image_name).maxpixel) #Show avepixel image

    #saveImage(image_ave, 'ksd.bmp')


    # fig1 = plt.subplot(1, 2, 1)
    # fig1.imshow(image_k, cmap=plt.cm.gray, interpolation='nearest')
    # fig1.set_title('K-frame image')


    # fig2 = plt.subplot(1,2, 2)
    # fig2.imshow(image_ave, cmap=plt.cm.gray, interpolation='nearest')
    # fig2.set_title('Average image')
    # plt.show()

    #makeGIF(image_name, 143, 160)
    #makeGIF("FF451_20140811_005403_484_0472320.bin", 169, 189)

    #batchgif_test = [["FF453_20140808_002244_870_0468224.bin", (143, 160)], ["FF459_20140808_234407_189_0429568.bin", (230, 251)]]

    #makeGIF(batchgif_test)

    #make_night_GIF("C:\\Users\\Admin\\Desktop\\PER_GIF_making\\PUA_2014081213-Processed")

    #makeGIF("C:\\Users\\Admin\\Desktop\\PER_GIF_making\\PUA_2014081213-Processed\\FF451_20140812_221530_133_0312320.bin", 68, 112, print_name = False)

    #img_name = "FF453_20140808_002244_870_0468224.bin"
    #colorized_frame = colorize_maxframe(img_name)
    #saveImage(colorized_frame, img_name+'_colorized.bmp', print_name = False)


    # REGARDING FLATFIELDING AND LIGHTCURVE MAKING:

    #flat_dir = "C:\\Users\\Admin\\Desktop\\PER_GIF_making\\PUA_2014081213-Processed\\"
    #flat_dir = "C:\\Users\\Admin\\Desktop\\PER_GIF_making\\PUA_flat\\"
    #flat_dir = "C:\\Users\\Admin\\Desktop\\Pula_kowa\\calib_median\\"
    #flat_dir = "flat_sample3\\"
    #flat_dir = "C:\\Users\\Admin\\Desktop\\155mm_FlatTests\\Detections\\"

    #Flat_frame, Flat_frame_scalar = make_flat_frame(flat_dir, flat_save = "calib_frame.bmp", col_corrected = False)

    #img_name = "FF451_20140812_221530_133_0312320.bin"

    #img_max = readFF(flat_dir + img_name).maxpixel

    #saveImage(img_max, flat_dir+img_name+"_original.bmp", print_name = False)
    #start = time.clock()
    #leveled = adjust_levels(img_max, 23, 1.36, 102)
    #end = time.clock()
    #log.info(end-start)
    #saveImage(leveled, flat_dir+img_name+"_leveled.bmp", print_name = False)

    #saveImage(colorize_maxframe(flat_dir+img_name), 'color_test_fast.bmp', print_name = False)
    #saveImage(readFF(flat_dir+img_name).avepixel, flat_dir+'flat.bmp', print_name=False)

    # Flat_frame, Flat_frame_scalar = load_flat(flat_dir+"calib_frame.bmp")

    # for bin in os.listdir(flat_dir):
    #   if bin.split('.')[-1] == 'bin':
    #       saveImage(readFF(flat_dir+bin).maxpixel, flat_dir+bin+'_raw_max.bmp', print_name = False)
    #       saveImage(readFF(flat_dir+bin).avepixel, flat_dir+bin+'_raw_ave.bmp', print_name = False)
    #       saveImage(pr
    # ocess_avepixel(flat_dir+bin, Flat_frame, Flat_frame_scalar), flat_dir+bin+'_processed.bmp', print_name = False)
    #       log.info(bin + ' processed!')

    #img_dir = "C:\\Users\\Admin\\Desktop\\155mm_FlatTests\\CalibImg\\"
    #img_name = "FF451_20140816_212455_562_0055808.bin"
    #saveImage(process_maxframe(img_dir+img_name, Flat_frame, Flat_frame_scalar), img_dir+img_name+"_proc.bmp", print_name = False)

    #saveImage(process_avepixel(img_dir+img_name, Flat_frame, Flat_frame_scalar), img_dir+img_name+"_avg_proc.bmp", print_name = False)


    #img_dir = "C:\\Users\\Admin\\Desktop\\CAMS\\CapturedFiles\\"
    #img_name = "FF451_20140819_004945_593_0416256.bin"
    #get_processed_frames(img_dir+img_name, 1, None, None, None, 143, 151)

    #img_name = "00000255.bmp" #Skypatrol
    #get_processed_frames(img_dir+img_name, 2, None, None, None, 114, 145)




    #Flat_frame, Flat_frame_scalar = load_flat(flat_dir+"flat.bmp")

    #img_name = "FF300_20140802_195545_131_0001024.bin"
    #img_max = readFF(flat_dir+img_name).avepixel


    #img_name = "FF451_20140812_221530_133_0312320.bin"

    #det_only = get_detection_only(img_name, 68, 112)
    #det_only = get_detection_only(img_name, 200, 220)

    #saveImage(det_only, "1_detection_test2.bmp")




    #saveImage(readFF(flat_dir+"FF451_20140812_221530_133_0312320.bin").maxpixel, 'FF_raw.bmp', print_name = False)

    #makeGIF("C:\\Users\\Admin\\Desktop\\PER_GIF_making\\PUA_2014081213-Processed\\FF451_20140812_221530_133_0312320.bin", 68, 112, print_name = False, flat_frame = Flat_frame, Flat_frame_scalar = Flat_frame_scalar)

    #ff_bin = "FF451_20140812_190215_928_0022528.bin"


    #meteor_array = rotate_n_crop(ff_bin, flat_dir, Flat_frame, Flat_frame_scalar)

    # lightcurve_list = get_lightcurve(meteor_array)

    # newfile = open("lightcurve_list.txt", "w")
    # newfile.write(",".join(map(str, lightcurve_list)))
    # newfile.close()

    # plt.scatter(range(len(lightcurve_list)), lightcurve_list)
    # plt.savefig(ff_bin+'_lightcurve.png', bbox_inches='tight')
    # plt.show()



    #saveImage(Flat_frame, flat_dir+os.sep+"flat.bmp", print_name = False) #Save flat image

    # #Process all images
    # for ff_file_name in flat_raw:
    #   log.info("Processing "+ff_file_name)
    #   ff_file_image = readFF(ff_file_name).maxpixel

    #   sub_img = np.subtract(ff_file_image, Flat_frame) #Substract the Flat_frame from raw image

    #   result_img = deinterlace_blend(add_scalar(sub_img, Flat_frame_scalar)) #Step up the levels of substracted images by the average of the Flat_frame and deinterlace

    #   saveImage(ff_file_image, ff_file_name+"_unprocessed.bmp", print_name = False)
    #   #saveImage(Flat_frame, ff_file_name+"_Flat_frame.bmp", print_name = False)
    #   saveImage(result_img, ff_file_name+"_result.bmp", print_name = False)


    # image_name = flat_raw[0]
    # image_ave = readFF(image_name).avepixel #Show avepixel image

    #fig1 = plt.subplot(1, 1, 1)
    #fig1.imshow(result_img, cmap=plt.cm.gray, interpolation='nearest', vmin = 0, vmax = 255)
    #plt.show()



    # # Mark detections
    # img_name = "FF451_20140819_011805_796_0458752.bin"
    # coordinates = get_FTPdetect_coordinates("FTPdetectinfo_0451_2014_08_18.txt", img_name, 1)[0]

    # markedImage = markDetections(readFF(img_name).maxpixel, coordinates)

    # saveImage(markedImage, img_name+"_MARKED.bmp", print_name = False)


    # ## Test croping segments
    # img_name = "FF451_20140819_013054_156_0477952.bin"

    # seg_list = get_FTPdetect_coordinates(open("FTPdetectinfo_0451_2014_08_18.txt").readlines(), img_name, 3)

    # cropDetectionSegments(readFF(img_name), seg_list)
