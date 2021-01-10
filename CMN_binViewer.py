#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright notice (Revised BSD License)

# Copyright (c) 2016, Denis Vida
# Copyright (c) 2012, Almar Klein, Ant1, Marius van Voorden (images2gif.py)
# All rights reserved.
# Redistribution and use in source and binary forms, with or without modification, are permitted provided 
# that the following conditions are met:
# •   Redistributions of source code must retain the above copyright notice, this list of conditions and the 
#     following disclaimer.
# •   Redistributions in binary form must reproduce the above copyright notice, this list of conditions and 
#     the following disclaimer in the documentation and/or other materials provided with the distribution.
# •   Neither the name of the Croatian Meteor Network nor the names of its contributors may be used to 
#     endorse or promote products derived from this software without specific prior written permission.

# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED 
# WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANT ABILITY AND FITNESS FOR A 
# PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL DENIS VIDA BE LIABLE FOR ANY DIRECT, INDIRECT, 
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF 
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND 
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR 
# OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH 
# DAMAGE.

import os
import sys
import errno
import argparse
import gc
import glob
import time
import datetime
import subprocess

# python 2/3 compatability
if sys.version_info[0] < 3:
    import Tkinter as tk
    import tkFileDialog
    import tkMessageBox
    from Tkinter import IntVar, BooleanVar, StringVar, DoubleVar, Frame, ACTIVE, END, Listbox, Menu, \
        PhotoImage, NORMAL, DISABLED, Entry, Scale, Button
    from ttk import Label, Style, LabelFrame, Checkbutton, Radiobutton, Scrollbar
else:
    import tkinter as tk
    import tkinter.filedialog as tkFileDialog
    import tkinter.messagebox as tkMessageBox
    from tkinter import IntVar, BooleanVar, StringVar, DoubleVar, Frame, ACTIVE, END, Listbox, Menu, \
        PhotoImage, NORMAL, DISABLED, Entry, Scale, Button
    from tkinter.ttk import Label, Style, LabelFrame, Checkbutton, Radiobutton, Scrollbar

import threading
import logging
import logging.handlers
import traceback
from shutil import copy2

import wx

import numpy as np
from PIL import Image as img
from PIL import ImageTk
from PIL import ImageChops

from FF_bin_suite import readFF, buildFF, colorize_maxframe, max_nomean, load_dark, load_flat, process_array, \
    saveImage, make_flat_frame, makeGIF, get_detection_only, get_processed_frames, adjust_levels, \
    get_FTPdetect_coordinates, markDetections, deinterlace_array_odd, deinterlace_array_even, rescaleIntensity
from module_confirmationClass import Confirmation
import module_exportLogsort as exportLogsort
from module_highlightMeteorPath import highlightMeteorPath

version = 3.00  # python 2 and 3 compatability

# Disable video in Python 3
# Video inside the GUI is very prone to crashes due to TkInter being not thread-safe. Thus it is better to
# leave the video disabled

if sys.version_info[0] < 3:
    disable_UI_video = False
else:
    disable_UI_video = True

disable_UI_video = False

global_bg = "Black"
global_fg = "Gray"

config_file = 'config.ini'

log_directory = 'CMN_binViewer_logs'

tempImage = 0


def getSysTime():
    if sys.version_info[0] < 3:
        return time.clock()
    else:
        return time.process_time()


def mkdir_p(path):
    """ Makes a directory and handles all errors.
    """
    try:
        os.makedirs(path)
    except OSError as exc:
        if exc.errno == errno.EEXIST:
            pass
        else: 
            raise


class StyledButton(Button):
    """ Button with style. 
    """
    def __init__(self, *args, **kwargs):
        Button.__init__(self, *args, **kwargs)

        self.configure(foreground = global_fg, background = global_bg, borderwidth = 3)


class StyledEntry(Entry):
    """ Entry box with style. 
    """
    def __init__(self, *args, **kwargs):
        Entry.__init__(self, *args, **kwargs)

        self.configure(foreground = global_fg, background = global_bg, insertbackground = global_fg, disabledbackground = global_bg, disabledforeground = "DimGray")


class ConstrainedEntry(StyledEntry):
    """ Entry box with constrained values which can be input (e.g. 0-255).
    """
    def __init__(self, *args, **kwargs):
        StyledEntry.__init__(self, *args, **kwargs)
        self.maxvalue = 255
        vcmd = (self.register(self.on_validate), "%P")
        self.configure(validate="key", validatecommand=vcmd)
        # self.configure(foreground = global_fg, background = global_bg, insertbackground = global_fg)

    def disallow(self):
        """ Pings a bell on values which are out of bound.
        """
        self.bell()

    def update_value(self, maxvalue):
        """ Updates values in the entry box.
        """
        self.maxvalue = maxvalue
        vcmd = (self.register(self.on_validate), "%P")
        self.configure(validate="key", validatecommand=vcmd)

    def on_validate(self, new_value):
        """ Checks if entered value is within bounds.
        """
        try:
            if new_value.strip() == "":
                return True
            value = int(new_value)
            if value < 0 or value > self.maxvalue:
                self.disallow()
                return False
        except ValueError:
            self.disallow()
            return False

        return True


class Video(threading.Thread): 
    """ Class for handling video showing in another thread.
    """
    def __init__(self, viewer_class, img_path):
        
        super(Video, self).__init__()
        # Set main binViewer class to be callable inside Video class
        self.viewer_class = viewer_class
        self.img_path = img_path
        self.fps = self.viewer_class.fps.get()

        self.temp_frame = self.viewer_class.temp_frame.get()
        self.end_frame = self.viewer_class.end_frame.get()
        self.start_frame = self.viewer_class.start_frame.get()

        self.data_type = self.viewer_class.data_type.get()

        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):

        temp_frame = self.temp_frame
        start_frame = self.start_frame
        end_frame = self.end_frame

        video_cache = []  # Storing the fist run of reading from file to an array

        ff_bin_read = readFF(self.img_path, datatype=self.data_type)

        resize_fact = self.viewer_class.image_resize_factor.get()
        if resize_fact <= 0:
            resize_fact = 1        

        # Cache everything under 75 frames
        if (end_frame - start_frame + 1) <= 75:
            cache_flag = True
        else:
            cache_flag = False

        print('entering loop, _stop_event is', self._stop_event.is_set())

        while self._stop_event.is_set() is False: 
            # print('1')
            start_time = getSysTime()   # Time the script below to achieve correct FPS
            if temp_frame >= end_frame:
                self.temp_frame = start_frame
                temp_frame = start_frame
            else:
                temp_frame += 1
            # print('2')
            if cache_flag is True:
                
                # Cache video files during first run
                if len(video_cache) < (end_frame - start_frame + 1):
                    img_array = buildFF(ff_bin_read, temp_frame, videoFlag = True)
                    video_cache.append(img_array)
                else:
                    img_array = video_cache[temp_frame - start_frame] # Read cached video frames in consecutive runs

            else:
                img_array = buildFF(ff_bin_read, temp_frame, videoFlag = True)

            self.viewer_class.img_data = img_array

            # Prepare image for showing
            temp_image = ImageTk.PhotoImage(img.fromarray(img_array).resize((img_array.shape[1] // resize_fact, img_array.shape[0] // resize_fact), img.BILINEAR))

            self.viewer_class.imagelabel.configure(image = temp_image) #Set image to image label
            self.viewer_class.imagelabel.image = temp_image
            # print('3f')

            # Set timestamp
            # print('4')
            _, img_name = os.path.split(self.img_path)
            self.viewer_class.set_timestamp(temp_frame, image_name=img_name)
            # print('5')

            # Sleep for 1/FPS with corrected time for script running time
            end_time = getSysTime()
            script_time = float(end_time - start_time)
            # Don't run sleep if the script time is bigger than FPS
            time.sleep(max(0.01, (1.0 / self.fps) - script_time))
            # print('6')
            if self._stop_event.is_set() is True:
                print('stopped set true')
                break

        print('end of video loop')


class ExternalVideo(Frame): 
    """ Class for handling external video showing in another window.
    """

    def __init__(self, parent):
        Frame.__init__(self, parent, bg = global_bg)  
        parent.configure(bg = global_bg) # Set backgound color
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(0, weight=1)


        self.grid(sticky="NSEW") # Expand frame to all directions

        self.parent = parent

        self.parent.title("External video")

        # Video label
        blankImage = None
        self.externalVideoLabel = Label(self, image = blankImage)
        self.externalVideoLabel.image = blankImage
        self.externalVideoLabel.grid(row = 1, column = 1)

    def update(self, img_path, current_image, start_frame, end_frame, fps, data_type, dimensions=1, min_lvl=0,
                gamma=1, max_lvl=255, external_guidelines=0, HT_rho=0, HT_phi=0):
        """ Updates external video parameters on image change and runs the video.
        """
        self.img_path = img_path
        self.fps = fps
        self.dimensions = dimensions

        self.external_video_FFbinRead = readFF(img_path, datatype=data_type)

        # Apply levels and gamma
        self.external_video_FFbinRead.maxpixel = adjust_levels(self.external_video_FFbinRead.maxpixel, 
                                                                min_lvl, gamma, max_lvl)

        self.external_video_FFbinRead.avepixel = adjust_levels(self.external_video_FFbinRead.avepixel, 
                                                                min_lvl, gamma, max_lvl)

        if external_guidelines:
            # Draw meteor guidelines
            self.external_video_FFbinRead.avepixel = highlightMeteorPath(self.external_video_FFbinRead.avepixel, 
                                                                            HT_rho, HT_phi)

        self.external_video_ncols = self.external_video_FFbinRead.ncols - 1
        self.external_video_nrows = self.external_video_FFbinRead.nrows - 1

        if dimensions == 2:
            # 1.5 size external video
            self.external_video_ncols = int(self.external_video_ncols / 1.22474487139)
            self.external_video_nrows = int(self.external_video_nrows / 1.22474487139)
        elif dimensions == 3:
            # Half size external video
            self.external_video_ncols = int(self.external_video_ncols / 1.41421356237)
            self.external_video_nrows = int(self.external_video_nrows / 1.41421356237)
        elif dimensions == 4:
            # Quarter size external video
            self.external_video_ncols = int(self.external_video_ncols / 2)
            self.external_video_nrows = int(self.external_video_nrows / 2)

        # Set window size
        self.parent.geometry(str(self.external_video_ncols) + "x" + str(self.external_video_nrows))

        # Add a few frames to each side, to better see the detection
        start_temp = start_frame - 5
        end_temp = end_frame + 5

        start_frame = 0 if start_temp < 0 else start_temp

        if data_type == 1:
            
            # CAMS data type
            end_frame = 255 if end_temp > 255 else end_temp

        elif data_type == 2: 
            
            # Skypatrol data dype
            end_frame = 1500 if end_temp > 1500 else end_temp

        elif data_type == 3:

            # FITS file type
            end_frame = self.external_video_FFbinRead.nframes if end_temp > self.external_video_FFbinRead.nframes else end_temp




        self.external_video_startFrame = start_frame
        self.external_video_endFrame = end_frame
        self.external_video_counter = start_frame

        # Cache everything under 75 frames
        if (self.external_video_endFrame - self.external_video_startFrame + 1) <= 75:
            self.cache_flag = True
        else:
            self.cache_flag = False

        # Delete cache
        self.external_videoCache = None

        # Collect garbage and free memory
        gc.collect()

        self.external_videoCache = []

        self.external_video_FirstRun = True

        # Run external video
        self.run()

    def run(self):
        """ Run external video.
        """

        global stop_external_video

        start_time = getSysTime()  # Time the script below to achieve correct FPS

        if self.external_video_FirstRun:
            if self.cache_flag is True: 
                # Cache video files during first run
                img_array = buildFF(self.external_video_FFbinRead, self.external_video_counter, videoFlag = True)
                self.external_videoCache.append(img_array)

            else:
                img_array = buildFF(self.external_video_FFbinRead, self.external_video_counter, videoFlag = True)
        else:
            if self.cache_flag is True:
                img_array = self.external_videoCache[self.external_video_counter - self.external_video_startFrame] # Read cached video frames in consecutive runs
            else:
                img_array = buildFF(self.external_video_FFbinRead, self.external_video_counter, videoFlag = True)


        temp_image = ImageTk.PhotoImage(img.fromarray(img_array).resize((self.external_video_ncols, self.external_video_nrows), img.BILINEAR)) #Prepare for showing
        self.externalVideoLabel.configure(image = temp_image) #Set image to image label
        self.externalVideoLabel.image = temp_image

        # Deal with frame counter
        if self.external_video_counter == self.external_video_endFrame:
            self.external_video_counter = self.external_video_startFrame
            self.external_video_FirstRun = False
        else:
            self.external_video_counter += 1

        # Sleep for 1/FPS with corrected time for script running time
        end_time = getSysTime()

        script_time = float(end_time - start_time)

        if not script_time > 1.0 / self.fps:
            delay = 1.0 / self.fps - script_time
        else:
            delay = 0.001

        if not stop_external_video:
            self.after(int(delay * 1000), self.run)


class ConfirmationVideo(Frame):
    """ Class for handling Confirmation video showing in another window.
    """
    def __init__(self, parent):
        
        Frame.__init__(self, parent, bg = global_bg)  
        parent.geometry("256x256")
        parent.configure(bg = global_bg) # Set backgound color
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(0, weight=1)

        self.grid(sticky="NSEW") # Expand frame to all directions

        self.parent = parent

        self.parent.title("Detection centered video")

        # Video label
        blankImage = None
        self.confirmationVideoLabel = Label(self, image = blankImage)
        self.confirmationVideoLabel.image = blankImage
        self.confirmationVideoLabel.grid(row = 1, column = 1)

    def update(self, img_path, current_image, meteorNo, FTPdetectinfoContents, fps, data_type, cropSize = 64):
        """ Updates confirmation video parameters on image change and runs the video.
        """
        self.img_path = img_path
        self.cropSize = cropSize
        self.fps = fps

        self.confirmation_video_segmentList = get_FTPdetect_coordinates(FTPdetectinfoContents, current_image, meteorNo)
        self.confirmation_video_FFbinRead = readFF(img_path, datatype = data_type)

        self.confirmation_video_ncols = self.confirmation_video_FFbinRead.ncols - 1
        self.confirmation_video_nrows = self.confirmation_video_FFbinRead.nrows - 1

        self.confirmation_video_startFrame = 0
        self.confirmation_video_endFrame = len(self.confirmation_video_segmentList[0]) - 1
        self.confirmation_video_counter = 0

        # Delete cache
        self.confirmation_videoCache = None

        # Collect garbage and free memory
        gc.collect()

        self.confirmation_videoCache = []

        self.confirmation_video_FirstRun = True

        # Run confirmation video
        self.run()

    def run(self):
        """ Run the confirmation video.
        """

        global stop_confirmation_video

        cropSize = self.cropSize

        start_time = getSysTime()

        if self.confirmation_video_FirstRun:
            coordinate = self.confirmation_video_segmentList[0][self.confirmation_video_counter]

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
            x_end = cropSize * 2
            y_end = cropSize * 2

            fillZeoresFlag = False
            if x_left < 0:
                fillZeoresFlag = True
                x_diff = -x_left
                x_end = cropSize * 2
                x_left = 0

            if y_left < 0:
                fillZeoresFlag = True
                y_diff = -y_left
                y_end = cropSize * 2
                y_left = 0

            if x_right > self.confirmation_video_ncols:
                fillZeoresFlag = True
                x_diff = 0
                x_end = cropSize * 2 - (x_right - self.confirmation_video_ncols)

                x_right = self.confirmation_video_ncols

            if y_right > self.confirmation_video_nrows:
                fillZeoresFlag = True
                y_diff = 0
                y_end = cropSize * 2 - (y_right - self.confirmation_video_nrows - 1)

                y_right = self.confirmation_video_nrows + 1

            imageArray = buildFF(self.confirmation_video_FFbinRead, int(frame), videoFlag = True)

            # If croped area is in the corner, fill corner with zeroes
            if fillZeoresFlag:

                cropedArray = np.zeros(shape =(cropSize * 2, cropSize * 2))
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

            self.confirmation_videoCache.append(np.copy(cropedArray))

        else:
            cropedArray = self.confirmation_videoCache[self.confirmation_video_counter]

        tempImage = ImageTk.PhotoImage(img.fromarray(cropedArray).resize((256, 256), img.BICUBIC))  # Prepare for showing
        self.confirmationVideoLabel.configure(image = tempImage)  # Set image to image label
        self.confirmationVideoLabel.image = tempImage

        # Deal with frame counter
        if self.confirmation_video_counter == self.confirmation_video_endFrame:
            self.confirmation_video_counter = 0
            self.confirmation_video_FirstRun = False
        else:
            self.confirmation_video_counter += 1

        # Sleep for 1/FPS with corrected time for script running time
        end_time = getSysTime()

        script_time = float(end_time - start_time)
        slowFactor = 1.1
        if not script_time > slowFactor * 1.0 / self.fps:
            delay = slowFactor * 1.0 / self.fps - script_time
        else:
            delay = 0.001

        if not stop_confirmation_video:
            self.after(int(delay * 1000), self.run)


class SuperBind():
    """ Enable any key to have unique events on being pressed once or being held down longer.

        pressed_function is called when the key is being held down.
        release_function is called when the key is pressed only once or released after pressing it constantly

        Arguments:
            key - key to be pressed, e.g. 'a'
            master - 'self' from master class
            root - Tkinter root of master class
            pressed_function - function to be called when the key is pressed constantly
            release_function - function to be called when the key is released or pressed only once

            repeat_press - if True, pressed_function will be called before release_function on only one key press (default True)
            no_repeat_function - will be run if repeat_press is False (default is None)

        e.g. calling from master class:
        a_key = SuperBind('a', self, self.root, self.print_press, self.print_release)
    """

    def __init__(self, key, master, root, pressed_function, release_function, repeat_press = True, no_repeat_function = None):
        self.afterId = None
        self.master = master
        self.root = root
        self.repeat_press = repeat_press
        self.no_repeat_function = no_repeat_function

        self.pressed_function = pressed_function
        self.release_function = release_function

        self.root.bind('<KeyPress-' + key + '>', self.keyPress)
        self.root.bind('<KeyRelease-' + key + '>', self.keyRelease)

        self.pressed_counter = 0

    def keyPress(self, event):
        if self.afterId is not None:
            self.master.after_cancel(self.afterId)
            self.afterId = None
            self.pressed_function()
        else:
            if self.pressed_counter > 1:
                self.pressed_function()
            else:
                if self.repeat_press:
                    # When this is true, pressed function will be called and release function will be called both
                    self.release_function()
                else:
                    if self.no_repeat_function is not None:
                        # If a special function is provided, run it instead
                        self.no_repeat_function()

            self.pressed_counter += 1

    def keyRelease(self, event):
        self.afterId = self.master.after_idle(self.processRelease, event)

    def processRelease(self, event):
        self.release_function()
        self.afterId = None
        self.pressed_counter = 0


class SuperUnbind():
    """ Unbind all that was bound by SuperBind.
    """
    def __init__(self, key, master, root):
        self.master = master
        self.root = root

        self.root.unbind('<KeyPress-' + key + '>')
        self.root.unbind('<KeyRelease-' + key + '>')


class BinViewer(Frame):
    """ Main CMN_binViewer window.
    """
    def __init__(self, parent, dir_path=None, confirmation=False):
        """ Runs only when the viewer class is created (i.e. on the program startup only).

        Arguments:
            parent: [tk object] Tk root handle.

        Keyword arguments:
            dir_path: [str] If given, binviewer will open the given directory. None by default.
            confirmation: [bool] If True, BinViewer will start in confirmation mode. False by default.

        """

        # parent.geometry("1366x768")
        # strip off terminal slash if present

        if dir_path is not None:
            if dir_path[-1] == os.sep:
                dir_path = dir_path[:-1]

        Frame.__init__(self, parent, bg = global_bg)
        parent.configure(bg = global_bg)  # Set backgound color
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(0, weight=1)

        self.grid(sticky="NSEW")  # Expand frame to all directions
        # self.grid_propagate(0)

        self.parent = parent

        # DEFINE INITIAL VARIABLES

        self.filter_no = 6  # Number of filters
        self.dir_path = os.path.abspath(os.sep)

        self.layout_vertical = BooleanVar()  # Layout variable

        # Read configuration file
        orientation, fps_config, self.dir_path, external_video_config, edge_marker, external_guidelines, image_resize_factor = self.readConfig()

        # Image resize factor
        self.image_resize_factor = IntVar()
        self.image_resize_factor.set(image_resize_factor)

        if orientation == 0:
            self.layout_vertical.set(False)
        else:
            self.layout_vertical.set(True)

        self.mode = IntVar()
        self.minimum_frames = IntVar()
        self.minimum_frames.set(0)

        self.detection_dict = {}

        self.data_type_var = IntVar()  # For GUI
        self.data_type_var.set(0)  # Set to Auto

        self.data_type = IntVar()  # For backend
        self.data_type.set(1)  # Set to CAMS

        self.filter = IntVar()
        self.old_filter = IntVar()

        self.block_img_update = False
        self.img_data = 0
        self.current_image = ''
        self.current_image_cols = 768
        self.old_image = ''
        self.old_confirmation_image = ''
        self.img_name_type = 'maxpixel'

        self.dark_status = BooleanVar()
        self.dark_status.set(False)

        self.flat_status = BooleanVar()
        self.flat_status.set(False)

        self.dark_name = StringVar()
        self.dark_name.set("dark.bmp")

        self.flat_name = StringVar()
        self.flat_name.set("flat.bmp")

        self.deinterlace = BooleanVar()
        self.deinterlace.set(False)

        self.invert = BooleanVar()
        self.invert.set(False)

        self.hold_levels = BooleanVar()
        self.hold_levels.set(False)

        self.arcsinh_status = BooleanVar()
        self.arcsinh_status.set(False)

        self.sort_folder_path = StringVar()
        self.sort_folder_path.set("chosen")

        self.bin_list = StringVar()

        self.print_name_status = BooleanVar()
        self.print_name_status.set(False)

        self.start_frame = IntVar()
        self.start_frame.set(0)

        self.end_frame = IntVar()
        self.end_frame.set(255)

        self.temp_frame = IntVar()
        self.temp_frame.set(self.start_frame.get())

        self.stop_confirmation_video = BooleanVar()
        self.stop_confirmation_video.set(True)

        self.externalVideoOn = IntVar()
        self.externalVideoOn.set(external_video_config)

        self.HT_rho = 0
        self.HT_phi = 0

        self.edge_marker = IntVar()
        self.edge_marker.set(edge_marker)

        self.external_guidelines = IntVar()
        self.external_guidelines.set(external_guidelines)

        # GIF
        self.gif_embed = BooleanVar()
        self.gif_embed.set(False)

        self.repeat = BooleanVar()
        self.repeat.set(True)

        self.perfield_var = BooleanVar()
        self.perfield_var.set(False)

        self.fps = IntVar()
        self.fps.set(fps_config)

        # Levels
        self.gamma = DoubleVar()
        self.gamma.set(1.0)

        # Frames visibility
        self.save_image_frame = BooleanVar()
        self.save_image_frame.set(True)

        self.image_levels_frame = BooleanVar()
        self.image_levels_frame.set(True)

        self.save_animation_frame = BooleanVar()
        self.save_animation_frame.set(True)

        self.frame_scale_frame = BooleanVar()
        self.frame_scale_frame.set(False)
        self.old_animation_frame = BooleanVar()
        self.old_animation_frame.set(True)

        # Fast image change flag
        self.fast_img_change = False

        # Misc
        global readFF
        readFF = self.readFF_decorator(readFF)  # Decorate readFF function by also passing datatype, so that readFF doesn't have to be changed through the code

        # Initilize GUI
        self.initUI()

        # Bind key presses, window changes, etc. (key bindings)

        parent.bind("<Home>", self.move_top)
        parent.bind("<End>", self.move_bottom)

        # Call default bindings
        self.defaultBindings()

        parent.bind("<Left>", self.filter_left)
        parent.bind("<Right>", self.filter_right)

        parent.bind("<F1>", self.maxframe_set)
        parent.bind("<F2>", self.colorized_set)
        parent.bind("<F3>", self.detection_only_set)
        parent.bind("<F4>", self.avgframe_set)

        parent.bind("<F5>", self.odd_set)
        parent.bind("<F6>", self.even_set_toggle)
        parent.bind("<F7>", self.frame_filter_set)

        if not disable_UI_video:
            parent.bind("<F9>", self.video_set)

        parent.bind("<Delete>", self.deinterlace_toggle)
        parent.bind("<Insert>", self.hold_levels_toggle)

        parent.bind("<Return>", self.copy_bin_to_sorted)

        # Update UI changes
        parent.update_idletasks()
        parent.update()

        # If the directory path was given, open it
        if dir_path is not None:
            self.askdirectory(dir_path=dir_path)

        # Run confirmation if the flag was given
        if confirmation:
            self.confirmationStart()

    def defaultBindings(self):
        """ Default key bindings. User for program init and resetting after confirmation is done.
        """
        # Unbind possible old bindings
        SuperUnbind("Delete", self, self.parent)
        SuperUnbind("Prior", self, self.parent)
        SuperUnbind("Next", self, self.parent)

        # Go fast when pressing the key down (no image loading)
        SuperBind('Up', self, self.parent, lambda: self.fast_img_on('up'), lambda: self.fast_img_off('up'))
        SuperBind('Down', self, self.parent, lambda: self.fast_img_on('down'), lambda: self.fast_img_off('down'))

        self.parent.bind("<Prior>", self.capturedModeSet)  # Page up
        self.parent.bind("<Next>", self.detectedModeSet)  # Page down
        self.parent.bind("<Return>", self.copy_bin_to_sorted)  # Enter
        self.parent.bind("<Delete>", self.deinterlace_toggle)  # Deinterlace

    def readFF_decorator(self, func):
        """ Decorator used to pass self.data_type to readFF without changing all readFF statements in the code.
        """

        def inner(*args, **kwargs):
            if "datatype" in kwargs:
                return func(*args, **kwargs)
            else:
                return func(*args, datatype = self.data_type.get())

        return inner

    def correct_datafile_name(self, datafile):
        """ Returns True if the given string is a proper FF*.bin or Skypatrol name (depending on data type), else it returns false.
        """

        if self.data_type.get() == 1:

            # CAMS data type (OLD)
            if len(datafile) == 37:
                # e.g. FF451_20140819_003718_000_0397568.bin
                if datafile.count("_") == 4:
                    if datafile.split('.')[-1] == 'bin':
                        if datafile[0:2] == "FF":
                            return True, 1

            # CAMS data type (NEW)
            if len(datafile) == 41:
                # e.g. FF_000432_20161024_075333_209_0944384.bin
                if datafile.count("_") == 5:
                    if datafile.split('.')[-1] == 'bin':
                        if datafile[0:2] == "FF":
                            return True, -1

        elif self.data_type.get() == 2:

            # Skypatrol data type

            if len(datafile) == 12:
                # e.g. 00000171.bmp
                if datafile.split('.')[-1] == 'bmp':
                    return True, 0

        else:

            # FITS data type
            if datafile.lower().endswith('.fits'):
                if datafile.lower().startswith('ff'):
                    return True, -1

        return False

    def readConfig(self):
        """ Reads the configuration file.
        """

        orientation = 1
        fps = 25
        dir_path = self.dir_path
        external_video = 0
        edge_marker = 1
        external_guidelines = 1
        image_resize_factor = 1

        read_list = (orientation, fps)

        try:
            config_lines = open(config_file, 'r').readlines()
        except:
            tkMessageBox.showerror("Configuration file " + config_file + " not found! Program files are compromised!")
            return read_list

        for line in config_lines:
            if line[0] == '#' or line == '':
                continue
            line = line.split('#')[0].split('=')

            if 'orientation' in line[0]:
                orientation = int(line[1])

            if 'fps' in line[0]:
                fps = int(line[1])

            if 'dir_path' in line[0]:
                dir_path = line[1].strip()

            if 'external_video' in line[0]:
                external_video = int(line[1])

            if 'edge_marker' in line[0]:
                edge_marker = int(line[1])

            if 'external_guidelines' in line[0]:
                external_guidelines = int(line[1])

            if 'image_resize_factor' in line[0]:
                image_resize_factor = int(line[1])

        read_list = (orientation, fps, dir_path, external_video, edge_marker, external_guidelines, image_resize_factor)

        return read_list

    def write_config(self):
        """ Writes the configuration file.
        """
        orientation = int(self.layout_vertical.get())
        fps = int(self.fps.get())
        external_video = int(self.externalVideoOn.get())
        edge_marker = int(self.edge_marker.get())
        external_guidelines = int(self.external_guidelines.get())
        image_resize_factor = int(self.image_resize_factor.get())

        if fps not in (25, 30):
            fps = 25

        try:
            new_config = open(config_file, 'w')
        except:
            return False

        new_config.write("# Configuration file\n# DO NOT CHANGE VALUES MANUALLY\n\n")

        new_config.write("orientation = " + str(orientation) + " # 0 horizontal, 1 vertical\n")
        new_config.write("fps = " + str(fps) + "\n")
        new_config.write("image_resize_factor = " + str(image_resize_factor) + "\n")

        if ('CAMS' in self.dir_path) or ('Captured' in self.dir_path) or ('Archived' in self.dir_path):
            temp_path = self.dir_path
            new_path = []
            for line in temp_path.split(os.sep):
                if ('Captured' in line) or ('Archived' in line):
                    new_path.append(line)
                    break
                new_path.append(line)

            temp_path = (os.sep).join(new_path)

            # Write config parameters to config.ini, but check for non-ascii characters in the directory path
            try:
                new_config.write("dir_path = " + temp_path.strip() + "\n")
            except:
                # Non ascii - characters found
                tkMessageBox.showerror("Encoding error", "Make sure you don't have any non-ASCII characters in the path to your files. Provided path was:\n" + self.dir_path)
                sys.exit()

        new_config.write("external_video = " + str(external_video) + "\n")
        new_config.write("edge_marker = " + str(edge_marker) + "\n")
        new_config.write("external_guidelines = " + str(external_guidelines) + "\n")
        new_config.close()

        return True

    def update_data_type(self):
        """ Updates the data_type variable to match data type of directory content. If there are CAMS files,
            it returns 1, if the Skypatrol files prevail, it returns 2, and if fits pervial it returns 3.
        """

        # If changing during confirmation
        if self.mode.get() == 3:
            if self.confirmationEnd() == 0:
                return 0

        data_type_var = self.data_type_var.get()

        if data_type_var == 0:

            # Auto - determine data type
            bin_count = len(glob.glob1(self.dir_path, "FF*.bin"))
            bmp_count = len(glob.glob1(self.dir_path, "*.bmp"))
            fits_count = len(glob.glob1(self.dir_path, "FF*.fits"))

            dir_contents = os.listdir(self.dir_path)

            # If there is at least one FITS file inside, it's probably the RMS format
            if fits_count:

                # Set to RMS format
                self.data_type.set(3)
                self.end_frame.set(255)
                logimportstate='disabled'

            elif (bin_count >= bmp_count) or ("FTPdetectinfo_" in dir_contents):

                # Set to CAMS if there are more bin files
                self.data_type.set(1)
                self.end_frame.set(255)
                logimportstate='normal'

            elif (bmp_count >= bin_count):

                # Set to Skypatrol if there are more BMP files
                self.data_type.set(2)
                self.end_frame.set(1500)
                logimportstate='normal'

        elif data_type_var == 1:

            # CAMS
            self.data_type.set(1)
            self.end_frame.set(255)
            logimportstate='normal'

        elif data_type_var == 2:

            # Skypatrol
            self.data_type.set(2)
            self.end_frame.set(1500)
            logimportstate='normal'

        elif data_type_var == 3:

            # RMS FITS
            self.data_type.set(3)
            self.end_frame.set(255)
            logimportstate='disabled'

        # LOG
        self.fireballMenu.entryconfig("Export detection with background stars", state=logimportstate)
        self.fireballMenu.entryconfig("Export detection without background stars", state=logimportstate)
        # Update listbox
        self.update_listbox(self.get_bin_list())

        self.mode.set(1)
        self.filter.set(1)
        self.change_mode()
        self.move_top(0)  # Move listbox cursor to the top

        self.update_image(0)

    def update_layout(self):
        """ Updates the layout (horizontal/vertical).
        """

        self.menuBar.entryconfig("Window", state = "normal")

        # List of adjustable frames
        layout_frames = [self.save_image_frame, self.image_levels_frame, self.save_animation_frame, self.frame_scale_frame]
        enabled_frames = 0
        for frame in layout_frames:
            if frame.get() is True:
                enabled_frames -= 1

        # First column of vertical layout
        start_column = 3 + 3

        if self.layout_vertical.get() is True:
            # Vertical

            self.listbox.config(height = 37)  # Listbox size
            self.listbox.grid(row = 4, column = 0, rowspan = 7, columnspan = 2, sticky = "NS")  # Listbox position
            self.scrollbar.grid(row = 4, column = 2, rowspan = 7, sticky = "NS")  # Scrollbar size

            self.hold_levels_chk_horizontal.grid_forget()
            self.hold_levels_chk.grid(row = 6, column = 1, sticky = "W", pady=5)

            self.arcsinh_chk.grid_forget()
            self.arcsinh_chk.grid(row = 6, column = 2, sticky = "W", pady=5)

            # Check if Save image frame is enabled in Windows menu, if not, hide it
            if self.save_image_frame.get() is True:
                self.save_panel.grid(row = 8, column = start_column + enabled_frames, rowspan = 2, sticky = "NS", padx=2, pady=5, ipadx=3, ipady=3)
                enabled_frames += 1
                self.print_name_btn.grid(row = 9, column = 6, rowspan = 2)
            else:
                self.save_panel.grid_forget()

            # Check if Image levels frame is enabled in Windows menu, if not, hide it
            if self.image_levels_frame.get() is True:
                self.levels_label.grid(row = 8, column = start_column + enabled_frames, rowspan = 2, sticky = "NS", padx=2, pady=5, ipadx=3, ipady=3)
                enabled_frames += 1
            else:
                self.levels_label.grid_forget()

            # Check if Save animation frame is enabled in Windows menu, if not, hide it
            if self.save_animation_frame.get() is True:
                self.animation_panel.grid(row = 8, column = start_column + enabled_frames, rowspan = 2, columnspan = 1, sticky = "NS", padx=2, pady=5, ipadx=3, ipady=3)
                enabled_frames += 1
                self.gif_make_btn.grid(row = 9, column = 7, rowspan = 4, sticky = "NSEW")
            else:
                self.animation_panel.grid_forget()

            # Frame scale if filter "Frames" is chosen
            if self.frame_scale_frame.get() is True:
                self.frames_slider_panel.grid(row = 8, column = start_column + enabled_frames, rowspan = 2, sticky = "NS", padx=2, pady=5, ipadx=3, ipady=3)
                enabled_frames += 1
            else:
                self.frames_slider_panel.grid_forget()

        else:
            # Horizontal

            self.listbox.config(height = 30)  # Listbox size
            self.listbox.grid(row = 4, column = 0, rowspan = 7, columnspan = 2, sticky = "NS")  # Listbox position
            self.scrollbar.grid(row = 4, column = 2, rowspan = 7, sticky = "NS")  # Scrollbar size

            self.menuBar.entryconfig("Window", state = "disabled")

            self.hold_levels_chk.grid_forget()
            self.hold_levels_chk_horizontal.grid(row = 11, column = 4, columnspan = 2, sticky = "W")

            self.arcsinh_chk.grid_forget()
            self.arcsinh_chk.grid(row = 6, column = 1, sticky = "W", pady=5)

            self.save_panel.grid(row = 3, column = 6, rowspan = 1, sticky = "NEW", padx=2, pady=5, ipadx=3, ipady=3)
            self.print_name_btn.grid(row = 11, column = 3, rowspan = 1)

            self.animation_panel.grid(row = 4, column = 6, rowspan = 1, columnspan = 1, sticky = "NEW", padx=2, pady=5, ipadx=3, ipady=3)

            self.levels_label.config(width = 10)
            self.levels_label.grid(row = 5, column = 6, rowspan = 1, padx=2, pady=5, ipadx=3, ipady=3, sticky ="NEW")

            self.gif_make_btn.grid(row = 13, column = 4, rowspan = 2, columnspan = 2, sticky = "EW", padx=2, pady=5)

            self.frames_slider_panel.grid(row = 6, column = 6, rowspan = 1, padx=2, pady=5, ipadx=3, ipady=3, sticky ="NEW")

        self.write_config()

    def move_img_up(self, event):
        """ Moves one list entry up if the focus is not on the list, when the key Up is pressed.
        """

        moveImgLock = threading.RLock()
        moveImgLock.acquire()

        if self.listbox is not self.parent.focus_get():

            self.listbox.focus()

            try:
                cur_index = int(self.listbox.curselection()[0])
            except:
                moveImgLock.release()
                return None
            next_index = cur_index - 1
            if next_index < 0:
                next_index = 0

            self.listbox.activate(next_index)
            self.listbox.selection_clear(0, END)
            self.listbox.selection_set(next_index)
            self.listbox.see(next_index)

            self.update_image(1)

        # print('moved up!')
        moveImgLock.release()

    def move_img_down(self, event):
        """ Moves one list entry down if the focus is not on the list, when the key Down is pressed.
        """

        moveImgLock = threading.RLock()
        moveImgLock.acquire()

        if self.listbox is not self.parent.focus_get():

            self.listbox.focus()

            try:
                cur_index = int(self.listbox.curselection()[0])
            except:
                moveImgLock.release()
                return None
            next_index = cur_index + 1
            size = self.listbox.size() - 1
            if next_index > size:
                next_index = size

            self.listbox.activate(next_index)
            self.listbox.selection_clear(0, END)
            self.listbox.selection_set(next_index)
            self.listbox.see(next_index)

            self.update_image(1)

        moveImgLock.release()

    def move_top(self, event):
        """ Moves to the top entry when Home key is pressed.
        """
        moveImgLock = threading.RLock()
        moveImgLock.acquire()

        if self.listbox is not self.parent.focus_get():
            self.listbox.focus()

        self.listbox.activate(0)
        self.listbox.selection_clear(0, END)
        self.listbox.selection_set(0)
        self.listbox.see(0)

        moveImgLock.release()

        self.update_image(0)

    def move_bottom(self, event):
        """ Moves to the last entry when End key is pressed.
        """
        moveImgLock = threading.RLock()
        moveImgLock.acquire()

        if self.listbox is not self.parent.focus_get():
            self.listbox.focus()

        self.listbox.activate(END)
        self.listbox.selection_clear(0, END)
        self.listbox.selection_set(END)
        self.listbox.see(END)

        moveImgLock.release()

        self.update_image(0)

    def moveIndex(self, index):
        """Moves the list cursor to given index.
        """

        self.block_img_update = True

        moveImgLock = threading.RLock()
        moveImgLock.acquire()

        if self.listbox is not self.parent.focus_get():
            self.listbox.focus()

        self.listbox.activate(index)
        self.listbox.selection_clear(0, END)
        self.listbox.selection_set(index)
        self.listbox.see(index)

        moveImgLock.release()

        self.block_img_update = False

        self.update_image(0)

    def seeCurrent(self):
        """ Show current selection on listbox.
        """

        self.block_img_update = True

        # Index of current image in listbox
        cur_index = int(self.listbox.curselection()[0])

        self.listbox.see(cur_index)

        self.block_img_update = False

    def capturedModeSet(self, event):
        """ Change mode to captured.
        """
        self.mode.set(1)
        self.change_mode()

    def detectedModeSet(self, event):
        """ Change mode to detected.
        """
        self.mode.set(2)
        self.change_mode()

    def maxframe_set(self, event):
        """ Set maxframe filter by pressing F1.
        """
        if self.mode.get() != 2:  # Disabled in detections mode
            self.filter.set(1)
            self.update_image(0)

    def colorized_set(self, event):
        """ Set colored filter by pressing F2.
        """
        if self.mode.get() != 2:  # Disabled in detections mode
            self.filter.set(2)
            self.update_image(0)

    def detection_only_set(self, event):
        """ Set odd frame filter by pressing F4.
        """
        self.filter.set(3)
        self.update_image(0)

    def avgframe_set(self, event):
        """ Set odd frame filter by pressing F3.
        """
        if self.mode.get() != 2:  # Disabled in detections mode
            self.filter.set(4)
            self.update_image(0)

    def odd_set(self, event):
        """ Set odd frame filter by pressing F5.
        """
        if self.mode.get() != 2:  # Disabled in detections mode
            self.filter.set(5)
            self.update_image(0)

    def even_set_toggle(self, event):
        """Set even frame filter by pressing F6, an toggle with odd frame by further pressing.
        """
        if self.mode.get() != 2:  # Disabled in detections mode
            if self.filter.get() == 6:
                self.filter.set(5)
            else:
                self.filter.set(6)

            self.update_image(0)

    def frame_filter_set(self, event):
        """ Set Frame filter by pressing F7.
        """
        self.filter.set(7)
        self.update_image(0)

    def video_set(self, event):
        """ Sets VIDEO filter by pressing F9.
        """
        self.filter.set(10)
        self.update_image(0)

    def filter_left(self, event):
        """ Moves the filter field to the left.
        """
        if self.mode.get() != 2:
            # Disabled in detections mode
            next_filter = self.filter.get() - 1
            if next_filter < 1 or next_filter > self.filter_no:
                next_filter = self.filter_no
            self.filter.set(next_filter)
        else:
            # In detected mode
            self.filter.set(3)

        self.update_image(0)

    def filter_right(self, event):
        """ Moves the filter field to the right.
        """
        if self.mode.get() != 2:
            # Disabled in detections mode
            next_filter = self.filter.get() + 1
            if next_filter > self.filter_no:
                next_filter = 1
            self.filter.set(next_filter)
        else:
            # In detected mode
            self.filter.set(3)

        self.update_image(0)

    def deinterlace_toggle(self, event):
        """ Turns the deinterlace on/off.
        """
        if self.deinterlace.get() is True:
            self.deinterlace.set(False)
        else:
            self.deinterlace.set(True)

        self.update_image(0)

    def hold_levels_toggle(self, event):
        """ Toggle Hold levels button.
        """
        if self.hold_levels.get() is True:
            self.hold_levels.set(False)
        else:
            self.hold_levels.set(True)

    def dark_toggle(self, event):
        """Toggles the dark frame on/off.
        """
        if self.dark_status.get() is True:
            self.dark_status.set(False)
        else:
            self.dark_status.set(True)

        self.update_image(0)

    def open_dark_path(self):
        """ Opens dark frame via file dialog.
        """
        temp_dark = tkFileDialog.askopenfilename(initialdir = self.dir_path, parent = self.parent, title = "Choose dark frame file", initialfile = "dark.bmp", defaultextension = ".bmp", filetypes = [('BMP files', '.bmp')])
        if temp_dark != '':
            self.dark_name.set(temp_dark)

    def open_flat_path(self):
        """ Opens flat frame via file dialog.
        """
        temp_flat = tkFileDialog.askopenfilename(initialdir = self.dir_path, parent = self.parent, title = "Choose flat frame file", initialfile = "flat.bmp", defaultextension = ".bmp", filetypes = [('BMP files', '.bmp')])
        if temp_flat != '':
            self.flat_name.set(temp_flat)

    def flat_toggle(self, event):
        """Toggles the flat frame on/off.
        """
        if self.flat_status.get() is True:
            self.flat_status.set(False)
        else:
            self.flat_status.set(True)

        self.update_image(0)

    def update_current_image(self):
        """ Updates 2 varibales for tracking the current image, without changing the screen. Used for confirmation.
        """

        self.block_img_update = True

        updateImgLock = threading.RLock()
        updateImgLock.acquire()

        try:
            # Fix issue when sometimes nothing is selected
            cur_index = self.listbox.curselection()[0]
        except:
            cur_index = 0
            self.listbox.activate(cur_index)
            self.listbox.selection_clear(0, END)
            self.listbox.selection_set(cur_index)
            self.listbox.see(cur_index)

        self.current_image = self.listbox.get(cur_index)

        self.confirmationListboxEntry = " ".join(self.current_image.split()[0:2])

        # Modify current image for Confirmation mode
        if self.mode.get() == 3:
            self.current_image = self.current_image.split()[0]

        updateImgLock.release()

        self.block_img_update = False

    def fast_img_on(self, direction):
        """ Set flag for fast image change when key is being held down.
        """
        self.fast_img_change = True

        if self.listbox is not self.parent.focus_get():
            if direction == 'up':
                self.move_img_up(0)
            else:
                self.move_img_down(0)

    def fast_img_off(self, direction):
        """ Set flag for fast image change when key is being pressed once.
        """

        if self.listbox is not self.parent.focus_get():
            if direction == 'up':
                self.move_img_up(0)
            else:
                self.move_img_down(0)

        if self.fast_img_change:
            self.fast_img_change = False
            self.update_image(0)

    def update_image(self, event, update_levels = False):
        """ Updates the current image on the screen.
        """

        # Skip updating image when key is being held down
        if self.fast_img_change:
            return 0

        # Skip updating image on multiple consecutive updates
        if self.block_img_update:
            return 0

        # Confirmation video flags, app and window
        global stop_confirmation_video, confirmation_video_app, confirmation_video_root

        # External video flags, app and window
        global stop_external_video, external_video_app, external_video_root

        updateImageLock = threading.RLock()

        self.status_bar.config(text = "View image")  # Update status bar
        updateImageLock.acquire()
        try:
            # Check if the list is empty. If it is, do nothing.
            self.current_image = self.listbox.get(self.listbox.curselection()[0])
        except:
            return 0

        updateImageLock.release()

        try:
            print('update_image: stopping video thread')
            self.video_thread.stop()
            print('waiting')
            self.video_thread.join()  # Wait for the video thread to finish
            print('done...')
            self.video_thread = None  # Delete video thread
        except:
            self.video_thread = None  # Delete video thread
            pass

        # Only on image change, set proper ConstrainedEntry maximum values for Video and Frame filter start and end frames, only in Captured mode
        if (self.current_image != self.old_image) and self.mode.get() == 1:

            if (self.data_type.get() == 1) or (self.data_type.get() == 3):
                # CAMS/RMS
                # Set constrained entry max values
                self.start_frame_entry.update_value(255)
                self.end_frame_entry.update_value(255)
                self.frame_start_frame_entry.update_value(255)
                self.frame_end_frame_entry.update_value(255)

            else:
                # Skypatrol
                # Set constrained entry max values
                self.start_frame_entry.update_value(1500)
                self.end_frame_entry.update_value(1500)
                self.frame_start_frame_entry.update_value(1500)
                self.frame_end_frame_entry.update_value(1500)

        if self.mode.get() == 1:

            # Prepare for Captured mode
            if event == 1:

                # Set only when the image is changed
                self.start_frame.set(0)

                if (self.data_type.get() == 1) or (self.data_type.get() == 3):
                    # CAMS
                    self.end_frame.set(255)
                    self.frame_scale.config(to = 255)

                else:
                    # Skypatrol
                    self.end_frame.set(1500)
                    self.frame_scale.config(to = 1500)

        elif self.mode.get() == 2:
            # Detection mode preparations, find the right image and set the start and end frames into entry fields
            temp_img = self.detection_dict[self.current_image]  # Get image data

            self.current_image = temp_img[0]
            start_frame = temp_img[1][0]  # Set start frame
            end_frame = temp_img[1][1]  # Set end frame

            if (self.data_type.get() == 1) or (self.data_type.get() == 3):

                # Only on CAMS/RMS data type
                start_temp = start_frame - 5
                end_temp = end_frame + 5

            else:
                start_temp = start_frame
                end_temp = end_frame

            start_temp = 0 if start_temp < 0 else start_temp

            if (self.data_type.get() == 1) or (self.data_type.get() == 3):

                # CAMS data type
                end_temp = 255 if end_temp > 255 else end_temp

            else:
                # Skypatrol data dype
                end_temp = 1500 if end_temp > 1500 else end_temp
                self.meteor_no = temp_img[1][2]

            self.start_frame.set(start_temp)
            self.end_frame.set(end_temp)

        elif self.mode.get() == 3:
            # Prepare for confirmation

            self.confirmationListboxEntry = " ".join(self.current_image.split()[0:2])
            temp_info = self.confirmationDict[self.confirmationListboxEntry]

            # Prepare for plotting detections
            ffBinName, self.meteor_no = self.confirmationListboxEntry.split()
            detectionCoordinates, self.HT_rho, \
                self.HT_phi = get_FTPdetect_coordinates(self.ConfirmationInstance.FTPdetect_file_content,
                ffBinName, int(float(self.meteor_no)))

            # Change to Maxpixel filter after each image change
            if (self.old_confirmation_image != self.current_image) or (self.old_filter.get() in (7, 10)):
                stop_confirmation_video = True
                stop_external_video = True

                # Don't change to maxpixel if the image hasn't been changes
                # if (self.old_confirmation_image != self.current_image) and (not self.old_filter.get() in (7, 10)):
                if (self.old_confirmation_image != self.current_image):
                    self.filter.set(1)

                current_image, self.meteor_no = self.current_image.split()[0:2]

                # Start confirmation video
                if not self.filter.get() in (7, 10):
                    start_frame = temp_info[1]
                    end_frame = temp_info[2]

                    self.start_frame.set(start_frame)
                    self.end_frame.set(end_frame)

                    img_path = os.path.join(self.dir_path, current_image)

                    if confirmation_video_app is not None:
                        # Delete old confirmation app, to prepare for showing a new one
                        confirmation_video_app.destroy()
                        confirmation_video_app = None

                    if external_video_app is not None:
                        # Delete old external video app, to prepare for showing a new one
                        external_video_app.destroy()
                        external_video_app = None

                    if self.externalVideoOn.get() == 0:

                        stop_confirmation_video = False

                        if confirmation_video_root is not None:
                            # Run confirmation video
                            confirmation_video_app = ConfirmationVideo(confirmation_video_root)
                            confirmation_video_app.update(img_path, current_image, int(float(self.meteor_no)),
                                self.ConfirmationInstance.FTPdetect_file_content,
                                self.fps.get(), self.data_type.get())

                    if self.externalVideoOn.get():

                        stop_external_video = False

                        if external_video_root is not None:

                            # Read levels and gamma values
                            minv_temp = self.min_lvl_scale.get()
                            gamma_temp = self.gamma.get()
                            maxv_temp = self.max_lvl_scale.get()

                            # 1 - full size, 2 - half size, 3 - quarter size
                            dimensions = self.externalVideoOn.get()

                            # Run external video
                            external_video_app = ExternalVideo(external_video_root)
                            external_video_app.update(img_path, current_image, self.start_frame.get(),
                                self.end_frame.get(), self.fps.get(), self.data_type.get(),
                                dimensions, min_lvl = minv_temp, gamma = gamma_temp,
                                max_lvl = maxv_temp,
                                external_guidelines=self.external_guidelines.get(),
                                HT_rho = self.HT_rho, HT_phi = self.HT_phi)

                self.old_confirmation_image = self.current_image
            self.current_image, self.meteor_no = self.current_image.split()[0:2]

        img_path = os.path.join(self.dir_path, self.current_image)

        if not os.path.isfile(img_path):
            tkMessageBox.showerror("File error", "File not found:\n" + img_path)
            return 0

        dark_frame = None
        flat_frame = None
        flat_frame_scalar = None

        # Do if the dark frame is on
        if self.dark_status.get() is True:
            dark_path = self.dark_name.get()
            pth, dark_fname = os.path.split(dark_path)
            if pth == '':
                dark_path = os.path.join(self.dir_path, dark_fname)

            try:
                dark_frame = load_dark(dark_path)
            except:
                tkMessageBox.showerror("Dark frame file error", "Cannot find dark frame file: " + self.dark_name.get())
                self.dark_status.set(False)

        # Do if the flat frame is on
        if self.flat_status.get() is True:
            flat_path = self.flat_name.get()
            pth, flat_fname = os.path.split(flat_path)
            if pth == '':
                flat_path = os.path.join(self.dir_path, flat_fname)
            try:
                flat_frame, flat_frame_scalar = load_flat(flat_path)
            except:
                tkMessageBox.showerror("Flat frame file error", "Cannot find flat frame file: " + self.flat_name.get())
                self.flat_status.set(False)

        # Make changes if the filter has changed
        if self.old_filter.get() != self.filter.get():
            # Set all butons to be active
            self.dark_chk.config(state = NORMAL)
            self.flat_chk.config(state = NORMAL)
            self.deinterlace_chk.config(state = NORMAL)
            self.hold_levels_chk.config(state = NORMAL)
            self.arcsinh_chk.config(state = NORMAL)
            self.max_lvl_scale.config(state = NORMAL)
            self.min_lvl_scale.config(state = NORMAL)
            self.gamma_scale.config(state = NORMAL)
            self.invert_chk.config(state = NORMAL)

            self.windowMenu.entryconfig("Save animation", state = "normal")
            self.frame_scale_frame.set(False)
            self.save_animation_frame.set(self.old_animation_frame.get())
            self.update_layout()

            # Frames filter
            if self.filter.get() == 7:
                self.frame_scale.config(state = NORMAL)
                self.old_animation_frame.set(self.save_animation_frame.get())

            else:
                self.frame_scale.config(state = DISABLED)

        # Apply individual filters
        if self.filter.get() == 1:  # Maxpixel
            img_array = process_array(readFF(img_path).maxpixel, flat_frame, flat_frame_scalar, dark_frame, self.deinterlace.get())
            self.img_name_type = 'maxpixel'
            self.old_filter.set(1)

            # In Confirmation mode plot detection points
            if self.mode.get() == 3:

                # Mark detection points on the image
                img_array = markDetections(img_array, detectionCoordinates, self.edge_marker.get())

        elif self.filter.get() == 2:  # Colorized

            if (update_levels is True) or (self.hold_levels.get() is True):  # Adjust levels
                minv_temp = self.min_lvl_scale.get()
                gamma_temp = self.gamma.get()
                maxv_temp = self.max_lvl_scale.get()
            else:
                maxv_temp = None
                gamma_temp = None
                minv_temp = None

            # Disable check buttons, as these parameters are not used
            self.dark_chk.config(state = DISABLED)
            self.flat_chk.config(state = DISABLED)
            self.deinterlace_chk.config(state = DISABLED)

            img_array = colorize_maxframe(readFF(img_path), minv_temp, gamma_temp, maxv_temp)

            self.img_name_type = 'colorized'
            self.old_filter.set(2)

        elif self.filter.get() == 3:  # Detection only

            if self.mode.get() == 1:  # Captured mode
                self.dark_chk.config(state = DISABLED)
                self.deinterlace_chk.config(state = DISABLED)
                img_array = max_nomean(readFF(img_path), flat_frame, flat_frame_scalar)
                self.img_name_type = 'max_nomean'

            elif self.mode.get() == 2:  # Deteced mode
                self.dark_chk.config(state = NORMAL)
                self.deinterlace_chk.config(state = NORMAL)

                img_array = get_detection_only(readFF(img_path), self.start_frame.get(), self.end_frame.get(), flat_frame, flat_frame_scalar, dark_frame, self.deinterlace.get())
                self.img_name_type = 'detected_only'

            elif self.mode.get() == 3:  # Confirmation
                self.dark_chk.config(state = NORMAL)
                self.deinterlace_chk.config(state = NORMAL)

                # Get detections only image
                img_array = get_detection_only(readFF(img_path), self.start_frame.get(), self.end_frame.get(), flat_frame, flat_frame_scalar, dark_frame, self.deinterlace.get())
                self.img_name_type = 'detected_only'

            self.old_filter.set(3)

        elif self.filter.get() == 4:  # Average pixel
            img_array = process_array(readFF(img_path).avepixel, flat_frame, flat_frame_scalar, dark_frame, self.deinterlace.get())

            self.img_name_type = 'avepixel'
            self.old_filter.set(4)

        elif self.filter.get() == 5:  # Show only odd frame
            self.deinterlace_chk.config(state = DISABLED)
            img_array = process_array(readFF(img_path).maxpixel, flat_frame, flat_frame_scalar, dark_frame, deinterlace = False, field = 1)

            self.img_name_type = 'odd'
            self.old_filter.set(5)

        elif self.filter.get() == 6:  # Show only even frame
            self.deinterlace_chk.config(state = DISABLED)
            img_array = process_array(readFF(img_path).maxpixel, flat_frame, flat_frame_scalar, dark_frame, deinterlace = False, field = 2)

            self.img_name_type = 'even'
            self.old_filter.set(6)

        elif self.filter.get() == 7:
            # Show individual frames

            stop_confirmation_video = True
            stop_external_video = True

            # If filter wasn't changed
            if self.old_filter.get() != self.filter.get():
                self.windowMenu.entryconfig("Save animation", state = "disabled")
                self.save_animation_frame.set(False)
                self.frame_scale_frame.set(True)

                self.update_layout()

            # If the image or the filter has changed, set the scale to the start frame
            if (self.old_image != self.current_image) or (self.filter.get() != self.old_filter.get()):
                self.frame_scale.set(self.start_frame.get())

            img_array = process_array(buildFF(readFF(img_path), self.frame_scale.get()), flat_frame, flat_frame_scalar, dark_frame, self.deinterlace.get())

            self.set_timestamp(self.frame_scale.get())

            self.img_name_type = 'frame_' + str(self.frame_scale.get())
            self.old_filter.set(7)

        elif self.filter.get() == 10:
            # Show video

            if disable_UI_video:
                return 0

            stop_confirmation_video = True
            stop_external_video = True

            self.dark_chk.config(state = DISABLED)
            self.flat_chk.config(state = DISABLED)
            self.deinterlace_chk.config(state = DISABLED)
            self.hold_levels_chk.config(state = DISABLED)
            self.arcsinh_chk.config(state = DISABLED)
            self.max_lvl_scale.config(state = DISABLED)
            self.min_lvl_scale.config(state = DISABLED)
            self.gamma_scale.config(state = DISABLED)

            self.temp_frame.set(self.start_frame.get())  # Set temporary frame to start frame

            self.video_thread = Video(app, img_path)  # Create video object, pass binViewer class (app) to video object
            self.video_thread.daemon = True

            self.old_filter.set(10)

            self.video_thread.start()  # Start video thread

            return 0

        # Apply Enhance stars if on, or if the image is inverted
        if self.arcsinh_status.get() or self.invert.get():
            # Apply arcshin on an image
            limg = np.arcsinh(img_array)

            # Normalize values to 1
            limg = limg / limg.max()

            # Find low and high intensity percentiles
            low = np.percentile(limg, 0.1)
            high = np.percentile(limg, 99.8)

            # Rescale image levels with the given range
            img_array = (rescaleIntensity(limg, in_range=(low, high)) * 255).astype(np.uint8)

        # Adjust levels
        if (update_levels is True) or (self.hold_levels.get() is True):
            if self.filter.get() != 2:
                img_array = adjust_levels(img_array, self.min_lvl_scale.get(), self.gamma.get(), self.max_lvl_scale.get())

        elif self.hold_levels.get() is True:
            pass  # Don't reset values if hold levels button is on
        else:
            self.min_lvl_scale.set(0)
            self.max_lvl_scale.set(255)
            self.gamma_scale.set(0)
            self.gamma.set(1)

        updateImageLock.acquire()

        self.current_image_cols = len(img_array[0])

        self.img_data = img_array
        # temp_image = ImageTk.PhotoImage(img.fromarray(img_array.astype(np.uint8)).convert("RGB")) #Prepare for showing

        # Prepare for showing
        resize_fact = self.image_resize_factor.get()
        if resize_fact <= 0:
            resize_fact = 1
        imgdata = img.fromarray(img_array.astype(np.uint8)).resize((img_array.shape[1] // resize_fact, img_array.shape[0] // resize_fact), img.BILINEAR).convert("RGB")

        if self.invert.get():
            imgdata = ImageChops.invert(imgdata)
        temp_image = ImageTk.PhotoImage(imgdata)

        self.imagelabel.configure(image = temp_image)
        self.imagelabel.image = temp_image  # For reference, otherwise it doesn't work
        updateImageLock.release()

        # Generate timestamp
        if self.filter.get() != 7:
            self.set_timestamp()

        self.old_image = self.current_image

        return 0

    def set_timestamp(self, fps = None, image_name = None):
        """ Sets timestamp with given parameters.
        """

        timestampLock = threading.RLock()
        timestampLock.acquire()
        if fps is None:
            # fps = " FFF"
            fps = ""
        else:
            fps = str(fps).zfill(4)

        # Get image name from argument, if it was passed
        if image_name is not None:
            current_image = image_name
        else:
            current_image = self.current_image

        # Check if the given file has a standard file name
        correct_status, format_type = self.correct_datafile_name(current_image)

        # Extract the proper timestamp for the given data format
        if correct_status:
            if (self.data_type.get() == 1) or (self.data_type.get() == 3):

                x = current_image.split('_')

                # CAMS data type (OLD)
                if format_type > 0:
                    timestamp = x[1][0:4] + "-" + x[1][4:6] + "-" + x[1][6:8] + " " + x[2][0:2] + ":" \
                        + x[2][2:4] + ":" + x[2][4:6] + "." + x[3] + " " + fps

                # CAMS data type (NEW)
                elif format_type == -1:
                    timestamp = x[2][0:4] + "-" + x[2][4:6] + "-" + x[2][6:8] + " " + x[3][0:2] + ":" + x[3][2:4] + ":" + x[3][4:6] + "." + x[4] + " " + fps

                else:
                    timestamp = ""

            else:

                # Skypatrol data type
                img_path = os.path.join(self.dir_path, current_image)
                (mode, ino, dev, nlink, uid, gid, size, atime, mtime, ctime) = os.stat(img_path)
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S.000", time.gmtime(mtime)) + " " + fps

        else:
            # timestamp = "YYYY-MM-DD HH:MM.SS.mms  FFF"
            timestamp = "YYYY-MM-DD HH:MM.SS.mms"

        # Change the timestamp label
        self.timestamp_label.configure(text = timestamp)
        timestampLock.release()

    def wxDirchoose(self, initialdir, title, _selectedDir = '.'):
        """ Opens a dialog for choosing a directory.
        """
        _userCancel = ''

        _ = wx.App()

        dialog = wx.DirDialog(None, title, style=1, defaultPath=initialdir, pos=(10, 10))

        if dialog.ShowModal() == wx.ID_OK:
            _selectedDir = dialog.GetPath()
            return _selectedDir

        else:
            dialog.Destroy()

        return _userCancel

    def askdirectory(self, dir_path=''):
        """ Shows the directory dialog, open the directory in binviewer and returns a selected directoryname.

        Keyword arguments:
            dir_path: [str] Directory to open. If given, the file dialog will not be shown.
        """

        old_dir_path = self.dir_path

        self.dir_path = dir_path

        # If changing during confirmation
        if self.mode.get() == 3:
            # restore previous dir_path to avoid confirmationEnd crashing
            self.dir_path = old_dir_path
            if self.confirmationEnd() == 0:
                return 0
            # and now reset it back again
            self.dir_path = dir_path

        self.filter.set(1)

        # Stop video every image update
        try:
            self.video_thread.stop()
            # Wait for the video thread to finish
            print('waiting')
            self.video_thread.join()
            print('done')
            # Delete video thread
            self.video_thread = None
        except:
            pass

        self.status_bar.config(text = "Opening directory...")

        if self.dir_path == '':

            # Opens the file dialog
            self.dir_path = self.wxDirchoose(initialdir = old_dir_path,
                title = "Open the directory with FF files, then click OK")

        if self.dir_path == '':

            if os.path.exists(old_dir_path):
                self.dir_path = old_dir_path
            else:
                self.dir_path = os.getcwd()

        # Update listbox
        self.update_listbox(self.get_bin_list())

        self.update_data_type()

        # Update dir label
        self.parent.wm_title("CMN_binViewer: " + self.dir_path)
        self.mode.set(1)
        self.filter.set(1)
        self.change_mode()

        self.move_top(0)  # Move listbox cursor to the top

        self.write_config()

    def get_bin_list(self):
        """ Get a list of FF*.bin files in a given directory.
        """
        bin_list = [line for line in os.listdir(self.dir_path) if self.correct_datafile_name(line)]
        return bin_list

    def update_listbox(self, bin_list):
        """ Updates the listbox with the current entries.
        """
        self.listbox.delete(0, END)
        for line in sorted(bin_list):
            self.listbox.insert(END, line)

    def save_image(self, extension, save_as):
        """ Saves the current image with given extension and parameters.
        """

        current_image = self.listbox.get(ACTIVE)
        if current_image == '':
            tkMessageBox.showerror("Image error", "No image selected! Saving aborted.")
            return 0

        img_name = current_image + "_" + self.img_name_type + '.' + extension
        img_path = os.path.join(self.dir_path, img_name)
        if save_as is True:
            img_path = tkFileDialog.asksaveasfilename(initialdir = self.dir_path, parent = self.parent, title = "Save as...", initialfile = img_name, defaultextension = "." + extension)
            if img_path == '':
                return 0

        saveImage(self.img_data, img_path, self.print_name_status.get())

        self.status_bar.config(text = "Image saved: " + img_name)

    def copy_bin_to_sorted(self, event):
        """ Copies the current image FF*.bin file to the given directory.
        """
        if self.current_image == '':
            return 0

        sorted_dir = self.sort_folder_path.get()
        pth, sort_pth = os.path.split(sorted_dir)
        if pth == '':
            sorted_dir = os.path.join(self.dir_path, sort_pth)

        try:
            mkdir_p(sorted_dir)
        except:
            tkMessageBox.showerror("Path error", "The path does not exist or it is a root directory (e.g. C:\\): " + sorted_dir)
            return 0

        try:
            copy2(os.path.join(self.dir_path, self.current_image), os.path.join(sorted_dir, self.current_image))  # Copy the file
        except:
            tkMessageBox.showerror("Copy error", "Could not copy file: " + self.current_image)
            return 0

        self.status_bar.config(text = "Copied: " + self.current_image)  # Change the status bar

    def open_current_folder(self, event):
        """Opens current directory in windows explorer.
        """

        sorted_directory = self.sort_folder_path.get()
        pth, sort_pth = os.path.split(sorted_directory)
        if pth == '':
            sorted_directory = os.path.join(self.dir_path, sort_pth)
        try:
            if os.platform == 'win32':
                os.startfile(sorted_directory)
            else:
                opener ="open" if sys.platform == "darwin" else "xdg-open"
                subprocess.call(opener, sorted_directory)
        except:
            try:
                if os.platform == 'win32':
                    os.startfile(self.dir_path)
                else:
                    opener ="open" if sys.platform == "darwin" else "xdg-open"
                    subprocess.call(opener, self.dir_path)
            except:
                tkMessageBox.showerror("Path not found", "Sorted folder is not created!")
                return 1

        return 0

    def make_master_dark(self):
        """ Makes the master dark frame.
        """
        self.status_bar.config(text = "Making master dark frame, please wait...")

        dark_dir = self.wxDirchoose(initialdir = self.dir_path, title = "Open the directory with dark frames, then click OK")

        if dark_dir == '':
            self.status_bar.config(text = "Master dark frame making aborted!")
            return 0

        dark_file = tkFileDialog.asksaveasfilename(initialdir = dark_dir, parent = self.parent, title = "Choose the master dark file name", initialfile = "dark.bmp", defaultextension = ".bmp", filetypes = [('BMP files', '.bmp')])

        if dark_file == '':
            self.status_bar.config(text = "Master dark frame making aborted!")
            return 0

        if (dark_file != '') and (dark_dir != ''):
            if make_flat_frame(dark_dir, dark_file, col_corrected = False, dark_frame = False, data_type=self.data_type.get()) is False:
                tkMessageBox.showerror("Master dark frame", "The folder is empty!")
                self.status_bar.config(text = "Master dark frame failed!")
                return 0
        else:
            self.status_bar.config(text = "Files for master dark not chosen!")

        self.status_bar.config(text = "Master dark frame done!")

        tkMessageBox.showinfo("Master dark frame", "Master dark frame done!")

    def make_master_flat(self):
        """ Make master flat frame. A Directory which contains flat frames is chosen, file where flat frame will be saved, and an optional dark frame.
        """

        self.status_bar.config(text = "Making master flat frame, please wait...")

        flat_dir = self.wxDirchoose(initialdir = self.dir_path, title = "Open the directory with flat frames, then click OK")
        if flat_dir == '':
            self.status_bar.config(text = "Master flat frame making aborted!")
            return 0
        flat_file = tkFileDialog.asksaveasfilename(initialdir = flat_dir, parent = self.parent, title = "Choose the master flat file name", initialfile = "flat.bmp", defaultextension = ".bmp", filetypes = [('BMP files', '.bmp')])
        if flat_file == '':
            self.status_bar.config(text = "Master flat frame making aborted!")
            return 0

        dark_file = tkFileDialog.askopenfilename(initialdir = flat_dir, parent = self.parent, title = "OPTIONAL: Choose dark frame, if any. Click cancel for no dark frame.", initialfile = "dark.bmp", defaultextension = ".bmp", filetypes = [('BMP files', '.bmp')])

        if dark_file != '':
            dark_frame = load_dark(dark_file)
        else:
            dark_frame = False

        if make_flat_frame(flat_dir, flat_file, col_corrected = False, dark_frame = dark_frame, data_type=self.data_type.get()) is False:
            tkMessageBox.showerror("Master flat frame", "The folder is empty!")
            self.status_bar.config(text = "Master flat frame failed!")
            return 0

        self.status_bar.config(text = "Master flat frame done!")
        tkMessageBox.showinfo("Master flat frame", "Master flat frame done!")

    def fireball_deinterlacing_process(self, logsort_export=False, no_background=False):
        """ Process individual frames (from start frame to end frame) by applying calibartion and deinterlacing them field by field. Used for manual fireball processing.
        """

        current_image = self.current_image
        if current_image == '':
            tkMessageBox.showerror("Image error", "No image selected! Saving aborted.")
            return '', 0

        dark_frame = None
        flat_frame = None
        flat_frame_scalar = None

        if self.dark_status.get() is True:
            dark_path = os.path.join(self.dir_path, self.dark_name.get())
            try:
                dark_frame = load_dark(dark_path)
            except:
                pass

        if self.flat_status.get() is True:
            flat_path = os.path.join(self.dir_path, self.flat_name.get())
            try:
                flat_frame, flat_frame_scalar = load_flat(flat_path)
            except:
                pass

        self.status_bar.config(text ="Processing individual frames and fields...")

        save_path = self.wxDirchoose(initialdir = self.dir_path, title = "Open the directory where you want to save individual frames by field, then click OK")

        # Abort the process if no path is chosen
        if save_path == '':
            return '', 0

        image_list = get_processed_frames(os.path.join(self.dir_path, current_image), save_path, self.data_type.get(), flat_frame, flat_frame_scalar, dark_frame, self.start_frame.get(), self.end_frame.get(), logsort_export, no_background = no_background)

        if not logsort_export:
            tkMessageBox.showinfo("Saving progress", "Saving done!")

            self.status_bar.config(text ="Processing done!")

        return save_path, image_list

    def make_gif(self):
        """ Makes a GIF animation file with given options.
        """

        current_image = self.current_image
        if current_image == '':
            tkMessageBox.showerror("Image error", "No image selected! Saving aborted.")
            return 0

        dark_frame = None
        flat_frame = None
        flat_frame_scalar = None

        if self.dark_status.get() is True:
            dark_path = os.path.join(self.dir_path, self.dark_name.get())
            try:
                dark_frame = load_dark(dark_path)
            except:
                pass

        if self.flat_status.get() is True:
            flat_path = os.path.join(self.dir_path, self.flat_name.get())
            try:
                flat_frame, flat_frame_scalar = load_flat(flat_path)
            except:
                pass

        self.status_bar.config(text ="Making GIF, please wait... It can take up to 15 or more seconds, depending on the size and options")

        gif_name = current_image.split('.')[0] + "fr_" + str(self.start_frame.get()) + "-" + str(self.end_frame.get()) + ".gif"

        gif_path = tkFileDialog.asksaveasfilename(initialdir = self.dir_path, parent = self.parent, title = "Save GIF animation", initialfile = gif_name, defaultextension = ".gif")

        # Abort GIF making if no file is chosen
        if gif_path == '':
            return 0

        # Get the repeat variable (the animation will loop if True)
        repeat_temp = self.repeat.get()
        if (repeat_temp == 0) or (repeat_temp is False):
            repeat_temp = False
        else:
            repeat_temp = True

        # Adjust levels
        minv_temp = self.min_lvl_scale.get()
        gamma_temp = self.gamma.get()
        maxv_temp = self.max_lvl_scale.get()

        makeGIF(FF_input = current_image, start_frame = self.start_frame.get(), end_frame = self.end_frame.get(), ff_dir=self.dir_path, deinterlace = self.deinterlace.get(), print_name = self.gif_embed.get(), Flat_frame = flat_frame, Flat_frame_scalar = flat_frame_scalar, dark_frame = dark_frame, gif_name_parse = gif_path, repeat = repeat_temp, fps = self.fps.get(), minv = minv_temp, gamma = gamma_temp, maxv = maxv_temp, perfield = self.perfield_var.get(), data_type=self.data_type.get())

        self.status_bar.config(text ="GIF done!")

        tkMessageBox.showinfo("GIF progress", "GIF saved!")

        # Write FPS to config file
        self.write_config()

    def get_detected_list(self, minimum_frames = 0):
        """ Gets a list of FF_bin files from the FTPdetectinfo with a list of frames. Used for composing the image while in DETECT mode.

        minimum_frames: the smallest number of detections for showing the meteor
        """
        minimum_frames = int(self.minimum_frames.get())

        def get_frames(frame_list):
            """Gets frames for given FF*.bin file in FTPdetectinfo.
            """
            # Times 2 because len(frames) actually contains every half-frame also
            if len(frame_list) < minimum_frames * 2:
                ff_bin_list.pop()
                return None
            min_frame = int(float(frame_list[0]))
            max_frame = int(float(frame_list[-1]))
            ff_bin_list[-1].append((min_frame, max_frame))

        def convert2str(ff_bin_list):
            """ Converts list format: [['FF*.bin', (start_frame, end_frame)], ... ] to string format ['FF*.bin Fr start_frame - end_frame'].
            """
            str_ff_bin_list = []
            for line in ff_bin_list:
                str_ff_bin_list.append(line[0] + " Fr " + str(line[1][0]).zfill(3) + " - " + str(line[1][1]).zfill(3))

            return str_ff_bin_list

        ftpdetect_file = [line for line in os.listdir(self.dir_path) if ("FTPdetectinfo_" in line) and (".txt" in line) and ("original" not in line)]
        if len(ftpdetect_file) == 0:
            tkMessageBox.showerror("FTPdetectinfo error", "FTPdetectinfo file not found!")
            return False
        ftpdetect_file = ftpdetect_file[0]
        try:
            FTPdetect_file_content = open(os.path.join(self.dir_path, ftpdetect_file), 'r').readlines()
        except:
            tkMessageBox.showerror("File error", "Could not open file: " + ftpdetect_file)
            return False

        # Solving issue when no meteors are in the file
        if int(FTPdetect_file_content[0].split('=')[1]) == 0:
            return []

        ff_bin_list = []

        skip = 0
        frame_list = []
        for line in FTPdetect_file_content[12:]:

            if ("-------------------------------------------------------" in line):
                get_frames(frame_list)

            if skip > 0:
                skip -= 1
                continue

            line = line.replace('\n', '')

            if ("FF" in line) and ((".bin" in line) or (".fits" in line)):
                ff_bin_list.append([line.strip()])
                skip = 2
                frame_list = None
                frame_list = []
                continue

            frame_list.append(line.split()[0])

        # Check if there are no detections
        if len(frame_list) == 0:
            return [], []

        # Writing the last FF bin file frames in a list
        if '----' not in frame_list[-1]:
            get_frames(frame_list)

        # Converts list to a list of strings and returns it
        return ff_bin_list, convert2str(ff_bin_list)

    def get_logsort_list(self, logsort_name = "LOG_SORT.INF", minimum_frames = 0):
        """ Gets a list of BMP files from the LOG_SORT.INF with a list of frames. Used for composing the image while in DETECT mode.

            minimum_frames: the smallest number of detections for showing the meteor"""

        minimum_frames = int(self.minimum_frames.get())

        def get_frames(frame_list, met_no):
            """Gets frames for given BMP file in LOGSORT.
            """
            # Times 2 because len(frames) actually contains every half-frame also
            if len(frame_list) < minimum_frames * 2:
                image_list.pop()
                return None
            min_frame = int(float(frame_list[0]))
            max_frame = int(float(frame_list[-1]))
            image_list[-1].append((min_frame, max_frame, met_no))

        def convert2str(ff_bin_list):
            """ Converts list format: [['FF*.bin', (start_frame, end_frame)], ... ] to string format ['FF*.bin Fr start_frame - end_frame'].
            """
            str_ff_bin_list = []
            for line in ff_bin_list:
                str_ff_bin_list.append(line[0] + " Fr " + str(line[1][0]).zfill(4) + " - " + str(line[1][1]).zfill(4) + " meteorNo: " + str(line[1][2]).zfill(4))

            return str_ff_bin_list

        logsort_path = os.path.join(self.dir_path, logsort_name)

        if not os.path.isfile(logsort_path):
            tkMessageBox.showerror("LOG_SORT.INF error", "LOG_SORT.INF file not found!")

        try:
            logsort_contents = open(logsort_path, 'r').readlines()
        except:
            tkMessageBox.showerror("File error", "Could not open file: " + logsort_path)
            return False

        # Return empty list if logsort is empty
        if logsort_contents[5] == '999':
            return []

        image_list = []
        frame_list = []
        met_no = 0
        old_met = -1
        first = True
        for line in logsort_contents[5:]:

            if line == '999':
                break

            line = line.split()

            img_name = line[4].split('_')[1] + '.bmp'
            met_no = int(line[0])

            if img_name not in [image[0] for image in image_list] or old_met != met_no:
                if first is not True:
                    get_frames(frame_list, met_no)
                else:
                    first = False

                image_list.append([img_name])

                old_met = met_no
                frame_list = None
                frame_list = []
                continue

            frame_list.append(line[1])

        get_frames(frame_list, met_no)

        return image_list, convert2str(image_list)

    def update_scales(self, value):
        """ Updates the size of levels scales, to make the appearence that there are 2 sliders on one scale.
        """
        size_var = 0.8
        min_value = self.min_lvl_scale.get()
        max_value = self.max_lvl_scale.get()
        middle = (min_value + max_value) / 2

        min_size = middle * size_var
        max_size = (255 - middle) * size_var

        self.min_lvl_scale.config(from_ = 0, to = middle - 1, length = min_size)
        self.max_lvl_scale.config(from_ = middle + 1, to = 255, length = max_size)

        self.gamma.set(1 / 10**(self.gamma_scale.get()))
        self.gamma_scale.config(label = "Gamma:             " + "{0:.2f}".format(round(self.gamma.get(), 2)))

        self.update_image(0, update_levels = True)

    def change_mode(self):
        """ Changes the current mode.
        """
        if self.mode.get() == 1:
            # Captured mode

            # Enable all filters
            self.maxpixel_btn.config(state = NORMAL)
            self.colored_btn.config(state = NORMAL)
            self.avgpixel_btn.config(state = NORMAL)
            self.odd_btn.config(state = NORMAL)
            self.even_btn.config(state = NORMAL)

            # Disable the entry of minimum frame number
            self.min_frames_entry.config(state = DISABLED)

            # Set filter to maxframe
            self.filter.set(1)

            # Preserve the image position
            old_image = self.current_image

            temp_bin_list = self.get_bin_list()

            # Update listbox
            self.update_listbox(temp_bin_list)

            if old_image in temp_bin_list:
                temp_index = temp_bin_list.index(old_image)

                # Move to old image position
                self.moveIndex(temp_index)
            else:
                # Move listbox cursor to the top
                self.move_top(0)

            self.start_frame.set(0)

            if (self.data_type.get() == 1) or (self.data_type.get() == 3):

                # CAMS data type
                self.end_frame.set(255)
                self.frame_scale.config(to = 255)
            else:

                # Skypatrol data type
                self.end_frame.set(1500)
                self.frame_scale.config(to = 1500)

        elif self.mode.get() == 2:

            # Detected mode
            if (self.data_type.get() == 1) or (self.data_type.get() == 3):
                # CAMS data type

                # Get a list of FF*.bin files from FTPdetectinfo
                detected_list = self.get_detected_list()
            else:
                # Skypatrol data type
                detected_list = self.get_logsort_list()

            if detected_list is False:
                self.mode.set(1)
                return 0
            elif not detected_list:
                tkMessageBox.showinfo("FTPdetectinfo info", "No detections in the FTPdetectinfo file!")
                self.mode.set(1)
                return 0

            # Enable the entry of minimum frame number
            self.min_frames_entry.config(state = NORMAL)

            ff_bin_list, str_ff_bin_list = detected_list

            self.detection_dict = dict(zip(str_ff_bin_list, ff_bin_list))

            # Dont change if video filter was set
            if not self.filter.get() == 10:
                # Set filter to Detection only
                self.filter.set(3)

            # Disable all other filters
            self.maxpixel_btn.config(state = DISABLED)
            self.colored_btn.config(state = DISABLED)
            self.avgpixel_btn.config(state = DISABLED)
            self.odd_btn.config(state = DISABLED)
            self.even_btn.config(state = DISABLED)

            # Get old image name
            old_image = self.current_image

            self.update_listbox(str_ff_bin_list)
            try:
                temp_index = str_ff_bin_list.index([bin for bin in str_ff_bin_list if old_image in bin][0])
                # Move to old image position
                self.moveIndex(temp_index)
            except:
                # Move listbox cursor to the top
                self.move_top(0)

        elif self.mode.get() == 3:
            # Confirmation mode

            # Enable all filters
            self.maxpixel_btn.config(state = NORMAL)
            self.colored_btn.config(state = NORMAL)
            self.avgpixel_btn.config(state = NORMAL)
            self.odd_btn.config(state = NORMAL)
            self.even_btn.config(state = NORMAL)

            # Disable the entry of minimum frame number
            self.min_frames_entry.config(state = DISABLED)

            # Set filter to maxpixel
            self.filter.set(1)

            self.confirmationDict = self.ConfirmationInstance.getMeteorList()

            listbox_entries = []
            for key in self.confirmationDict:
                listbox_entries.append(key + ' ' + self.confirmationDict[key][0])

            self.update_listbox(listbox_entries)
            self.move_top(0)

    def confirmationStart(self):
        """ Begin with pre-confirmation preparations.
        """

        def _colorGenerator():
            """ Returns next color in the list on each call.
            """
            colors = ['lemon chiffon', 'cyan', 'snow', 'gold', 'turquoise1', 'maroon1']
            while 1:
                for color in colors:
                    yield color

        # Used for coloring same image detections with the same color
        colorGen = _colorGenerator()

        # Check if viewing Skypatrol images
        if self.data_type.get() == 2:
            tkMessageBox.showerror("Skypatrol", "Confirmation is only available for CAMS standard files!")
            return 0

        confirmationDirectoryName = "ConfirmedFiles"
        rejectionDirectoryName = "RejectedFiles"

        upDir, nightDir = os.path.split(self.dir_path)
        up2Dir, upDir = os.path.split(upDir)
        if upDir == "CapturedFiles":
            if not tkMessageBox.askyesno("Directory name", "Are you sure you want to do confirmation on CapturedFiles?"):
                return 0
        elif upDir != "ArchivedFiles":
            tkMessageBox.showerror("Directory error", "You can only do confirmation in ArchivedFiles or CapturedFiles directory!")
            return 0

        confirmationDirectory = os.path.join(up2Dir, confirmationDirectoryName, nightDir)
        mkdir_p(confirmationDirectory)

        rejectionDirectory = os.path.join(up2Dir, rejectionDirectoryName, nightDir)
        mkdir_p(rejectionDirectory)

        image_list = []
        ftp_detect_list = []

        # Find all FTPdetectinfo files in the directory
        for image in os.listdir(self.dir_path):
            if self.correct_datafile_name(image):
                image_list.append(image)
                continue
            if ('FTPdetectinfo' in image) and ('.txt' in image):
                ftp_detect_list.append(image)

        ftpDetectFile = ''

        # Check if there are several FTPdetectinfo files in the directory
        if len(ftp_detect_list) > 1:

            # Offer the user to choose from several FTPdetectinfo files

            # Open a new window with radiobuttons
            ftpdetectinfo_window = tk.Toplevel(self.parent)
            ftpdetectinfo_window.wm_title("Choose FTPdetectinfo")
            ftpdetectinfo_window.lift()
            ftpdetectinfo_window.configure(background=global_bg, padx=10, pady=10)

            # Add a label
            w = Label(ftpdetectinfo_window, text="""Several FTPdetectinfo files were found in the chosen directory. \nPlease choose which one do you want to use for Confirmation.\n""")
            w.pack()

            # Add radiobuttons
            ftp_choice = IntVar()
            ftp_choice.set(0)
            for i, ftpdetect_name in enumerate(ftp_detect_list):
                b = Radiobutton(ftpdetectinfo_window, text=ftpdetect_name, variable=ftp_choice, value=i)
                b.pack(anchor=tk.W)

            # Add a closing button
            b = Button(ftpdetectinfo_window, text="OK", command=lambda: ftpdetectinfo_window.destroy())
            b.pack()

            # Wait until the FTPdetectinfo file is chosen
            self.parent.wait_window(ftpdetectinfo_window)

            # Choose the selected FTPdetectinfo file
            ftpDetectFile = ftp_detect_list[ftp_choice.get()]

        elif len(ftp_detect_list) == 1:
            # Choose the only one found FTPdetectinfo file
            ftpDetectFile = ftp_detect_list[0]

        else:
            # If not FTPdetectinfo files were found, show an error message
            ftpDetectFile = ''

        if ftpDetectFile == '':
            tkMessageBox.showerror("FTPdetectinfo error", "No FTPdetectinfo file could be found in directory: " + self.dir_path)
            self.confirmationFinish()
            return 0

        self.ConfirmationInstance = Confirmation(image_list, os.path.join(self.dir_path, ftpDetectFile), confirmationDirectory, rejectionDirectory, minimum_frames = 0)

        # Cancel the confirmation if there are no detectins in the FTPdetectinfo file
        if len(self.ConfirmationInstance.img_dict) == 0:
            tkMessageBox.showinfo("FTPdetectinfo error", "There are no detections in the FTPdetectinfo file!")
            self.confirmationFinish()
            return 0

        if tkMessageBox.askyesno("Confirmation", "Confirmation key bindings:\n  Enter - confirm\n  Delete - reject\n  Page Up - jump to previous image\n  Page Down - jump to next image\n\nThere are " + str(len(self.ConfirmationInstance.getImageList(0))) + " images to be confirmed, do you want to proceed?"):

            # Set gamma a bit higher and turn on deinterlace
            self.hold_levels.set(True)
            # Set gamma to about 1.3, so the meteors are visible better
            self.gamma_scale.set(-0.12)
            self.gamma.set(1.32)
            self.deinterlace.set(False)  # not needed with progressive scan video

            # Disable mode buttons during confirmation
            self.captured_btn.config(state = DISABLED)
            self.detected_btn.config(state = DISABLED)

            # Start confirmation video
            if self.externalVideoOn.get() == 0:
                confirmationVideoInitialize(self.current_image_cols)

            # Start external video
            if self.externalVideoOn.get():
                externalVideoInitialize(self.current_image_cols)

            self.mode.set(3)
            self.change_mode()

            # Color same image detections with same color
            color_old_image = None
            for index, entry in enumerate(self.listbox.get(0, END)):
                entry = entry.split()
                if entry[0] != color_old_image:
                    current_color = next(colorGen)
                    color_old_image = entry[0]

                self.listbox.itemconfig(index, fg = current_color)

            # Change key binding
            self.parent.bind("<Return>", self.confirmationYes)  # Enter

            SuperUnbind("Delete", self, self.parent)
            # Enable fast rejection
            SuperBind("Delete", self, self.parent, lambda: self.confirmationNo(0, fast_img = True), lambda: self.confirmationNo(0, fast_img = False), repeat_press = False)

            # Unbind old bindings
            self.parent.unbind("<Prior>")  # Page up
            self.parent.unbind("<Next>")  # Page down

            # Jump to next FF bin with Page Up and Page down, not just next detection
            SuperBind('Prior', self, self.parent, lambda: self.confirmationJumpPreviousImage(0, fast_img = True), lambda: self.confirmationJumpPreviousImage(0, fast_img = False), repeat_press = False, no_repeat_function = self.seeCurrent)
            SuperBind('Next', self, self.parent, lambda: self.confirmationJumpNextImage(0, fast_img = True), lambda: self.confirmationJumpNextImage(0, fast_img = False), repeat_press = False, no_repeat_function = self.seeCurrent)

            # Disable starting confirmation
            self.confirmationMenu.entryconfig("Start", state = "disabled")
            self.confirmationMenu.entryconfig("End", state = "normal")

            # Disable confirmation video options
            self.confirmationMenu.entryconfig("Edge markers", state = "disabled")
            self.confirmationMenu.entryconfig("Meteor guidelines (external video)", state = "disabled")
            self.confirmationMenu.entryconfig("Detection centered video", state = "disabled")
            self.confirmationMenu.entryconfig("External video - 1:1 size", state = "disabled")
            self.confirmationMenu.entryconfig("External video - 1:1.5 size", state = "disabled")
            self.confirmationMenu.entryconfig("External video - 1:2 size", state = "disabled")
            self.confirmationMenu.entryconfig("External video - 1:4 size", state = "disabled")

            self.update_layout()

        else:
            self.confirmationFinish()

    def confirmationYes(self, event):
        """ Confirm current image in Confirmation instance.
        """

        confYesLock = threading.RLock()
        confYesLock.acquire()

        self.ConfirmationInstance.confirmImage(self.confirmationListboxEntry)

        newEntry = self.confirmationListboxEntry + " Y  "

        if self.listbox is not self.parent.focus_get():
            self.listbox.focus()

        cur_index = int(self.listbox.curselection()[0])

        self.listbox.insert(ACTIVE, newEntry)
        self.listbox.delete(ACTIVE)

        # Change text color to green
        self.listbox.itemconfig(cur_index, fg = 'green')

        next_index = cur_index + 1
        size = self.listbox.size() - 1

        if next_index > size:
            next_index = size

        self.listbox.activate(next_index)
        self.listbox.selection_clear(0, END)
        self.listbox.selection_set(next_index)
        self.listbox.see(next_index)

        self.update_image(0)

        # Detect list end
        if cur_index == self.listbox.size() - 1:
            self.confirmationEnd()

        confYesLock.release()

    def confirmationNo(self, event, fast_img = False):
        """ Reject current image in Confirmation instance.
        """

        # Set flag for fast image changing
        if fast_img:
            if not self.fast_img_change:
                self.fast_img_change = True
        else:
            if self.fast_img_change:
                self.fast_img_change = False
                self.update_image(0)

        confNoLock = threading.RLock()
        confNoLock.acquire()

        self.ConfirmationInstance.rejectImage(self.confirmationListboxEntry)

        newEntry = self.confirmationListboxEntry + "   N"

        if self.listbox is not self.parent.focus_get():
            self.listbox.focus()

        cur_index = int(self.listbox.curselection()[0])

        self.listbox.delete(cur_index)
        self.listbox.insert(cur_index, newEntry)

        # Change text color to green
        self.listbox.itemconfig(cur_index, fg = 'red')

        next_index = cur_index + 1
        size = self.listbox.size() - 1

        if next_index > size:
            next_index = size

        self.listbox.activate(next_index)
        self.listbox.selection_clear(0, END)
        self.listbox.selection_set(next_index)
        self.listbox.see(next_index)

        self.update_image(0)

        self.update_current_image()

        # Detect list end
        if cur_index == self.listbox.size() - 1:
            self.confirmationEnd()

        confNoLock.release()

    def confirmationJumpPreviousImage(self, event, fast_img = False):
        """ Jump to previous FF bin in confirmation, not just next detection.
        """

        if self.listbox is not self.parent.focus_get():
            self.listbox.focus()

        if fast_img:
            self.fast_img_change = True
        else:
            self.fast_img_change = False

        # Current image
        cur_image = self.current_image

        # Index of current image in listbox
        cur_index = int(self.listbox.curselection()[0])

        self.listbox.see(cur_index)

        listbox_entries = self.listbox.get(0, END)

        bottom_image = None

        # Go through all entries and find the first detecting on the previous image
        for entry in reversed(listbox_entries[:cur_index + 1]):
            temp_image = entry.split()[0]

            # Decrement current index
            if temp_image == cur_image:
                if not cur_index == 0:
                    cur_index -= 1
            else:
                if cur_index == 0:
                    # Break if reached first element in listbox
                    break

                # Jump over all same images until you reach the first one of the same
                if bottom_image != temp_image:
                    if bottom_image is None:
                        bottom_image = temp_image
                    else:
                        # Increment if found image that is the first detection of the same image and break
                        cur_index += 1
                        break

                cur_index -= 1

        self.listbox.activate(cur_index)
        self.listbox.selection_clear(0, END)
        self.listbox.selection_set(cur_index)
        self.listbox.see(cur_index)

        self.update_current_image()

        self.update_image(0)

    def confirmationJumpNextImage(self, event, fast_img = False):
        """ Jump to next FF bin in confirmation, not just next detection.
        """

        if self.listbox is not self.parent.focus_get():
            self.listbox.focus()

        if fast_img:
            self.fast_img_change = True
        else:
            self.fast_img_change = False

        # Current image
        cur_image = self.current_image

        # Index of current image in listbox
        cur_index = int(self.listbox.curselection()[0])

        # self.listbox.see(cur_index)

        listbox_entries = self.listbox.get(0, END)
        listbox_size = len(listbox_entries)

        if cur_index == listbox_size - 1:
            self.confirmationNo(0)
            return 0

        # Go through all entries and find the next image
        for entry in listbox_entries[cur_index:]:
            temp_image = entry.split()[0]

            # Increment current index
            if temp_image == cur_image:

                # self.listbox.activate(cur_index)
                # self.listbox.selection_clear(0, END)
                # self.listbox.selection_set(cur_index)
                # self.listbox.see(cur_index)
                self.confirmationNo(0, fast_img = True)

                if not cur_index >= listbox_size - 1:
                    cur_index += 1
            else:
                break

        if not fast_img:
            self.fast_img_change = False

        if cur_index >= listbox_size - 1:
            cur_index = listbox_size - 1

        # self.listbox.activate(cur_index)
        # self.listbox.selection_clear(0, END)
        # self.listbox.selection_set(cur_index)
        # self.listbox.see(cur_index)

        self.update_current_image()

        self.update_image(0)

    def confirmationEnd(self):
        """ Evoken when ending confirmation.

        It does post-confirmation cleaning up and asks the user whether to continue with confirmation or to save confirmed files.
        """

        unchecked_count = len(self.ConfirmationInstance.getImageList(0))

        if unchecked_count > 0:
            if tkMessageBox.askyesno("Confirmation", "Are you sure you want to exit confirmation? You still have " + str(unchecked_count) + " unchecked images."):
                if not tkMessageBox.askyesno("Confirmation", "Do you want to save confirmed images to ConfirmationFiles?"):
                    self.confirmationFinish()
                    return 2
            else:
                return 0

        confirmed_files = self.ConfirmationInstance.getImageList(1)
        confirmed_count = len(confirmed_files)
        rejected_files = self.ConfirmationInstance.getImageList(-1)
        rejected_count = len(rejected_files)

        FTPdetectinfoExport = self.ConfirmationInstance.exportFTPdetectinfo()

        # Copy confirmed images and write modified FTPdetectinfo, if any files were confirmed
        if len(confirmed_files):
            for ff_bin in confirmed_files:

                dir_contents = os.listdir(self.dir_path)

                if ff_bin in dir_contents:
                    copy2(os.path.join(self.dir_path, ff_bin), os.path.join(self.ConfirmationInstance.confirmationDirectory, ff_bin))

            for dir_file in dir_contents:
                file_name, file_ext = os.path.splitext(dir_file)
                file_ext = file_ext.lower()
                if ('FTPdetectinfo' in dir_file) and file_ext == '.txt' and not ('_original' in file_name):
                    copy2(os.path.join(self.dir_path, dir_file), os.path.join(self.ConfirmationInstance.confirmationDirectory, "".join(dir_file.split('.')[:-1]) + '_pre-confirmation.txt'))
                    continue
                elif file_ext in ('.txt', '.inf', '.rpt', '.log', '.cal', '.hmm', '.json') or dir_file == '.config':
                    copy2(os.path.join(self.dir_path, dir_file), os.path.join(self.ConfirmationInstance.confirmationDirectory, dir_file))

            # Write the filtered FTPdetectinfo content to a new file
            newFTPdetectinfo = open(os.path.join(self.ConfirmationInstance.confirmationDirectory, os.path.basename(self.ConfirmationInstance.FTP_detect_file)), 'w')
            for line in FTPdetectinfoExport:
                newFTPdetectinfo.write(line)

            newFTPdetectinfo.close()

        # Copy rejected images and original ftpdetectinfo
        if len(rejected_files):
            dir_contents = os.listdir(self.dir_path)
            for ff_bin in rejected_files:
                if ff_bin in dir_contents:
                    copy2(os.path.join(self.dir_path, ff_bin), os.path.join(self.ConfirmationInstance.rejectionDirectory, ff_bin))
            for dir_file in dir_contents:
                file_name, file_ext = os.path.splitext(dir_file)
                if file_ext in ('.txt', '.json') or dir_file == '.config':
                    copy2(os.path.join(self.dir_path, dir_file), os.path.join(self.ConfirmationInstance.rejectionDirectory, dir_file))

        tkMessageBox.showinfo("Confirmation", "Confirmation statistics:\n  Confirmed: " + str(confirmed_count) + "\n  Rejected: " + str(rejected_count) + "\n  Unchecked: " + str(unchecked_count))

        self.confirmationFinish()

        return 2

    def confirmationFinish(self):
        """ Finish confirmation procedure by reseting GUI settings to normal.
        """

        if self.externalVideoOn.get() == 0:
            # Kill confirmation video windows
            global confirmation_video_root
            if confirmation_video_root is not None:
                confirmation_video_root.destroy()
                confirmation_video_root = None
        else:
            # Kill external video windows
            global external_video_root
            if external_video_root is not None:
                external_video_root.destroy()
                external_video_root = None

        # Delete confirmation instance
        self.ConfirmationInstance = None

        # Set old confirmation image to None
        self.old_confirmation_image = None

        # Change key bindings to previous
        self.defaultBindings()

        # Re-enable mode buttons
        self.captured_btn.config(state = NORMAL)
        self.detected_btn.config(state = NORMAL)

        # Re-enable menu
        self.confirmationMenu.entryconfig("Start", state = "normal")
        self.confirmationMenu.entryconfig("End", state = "disabled")

        self.confirmationMenu.entryconfig("Edge markers", state = "normal")
        self.confirmationMenu.entryconfig("Meteor guidelines (external video)", state = "normal")
        self.confirmationMenu.entryconfig("Detection centered video", state = "normal")
        self.confirmationMenu.entryconfig("External video - 1:1 size", state = "normal")
        self.confirmationMenu.entryconfig("External video - 1:1.5 size", state = "normal")
        self.confirmationMenu.entryconfig("External video - 1:2 size", state = "normal")
        self.confirmationMenu.entryconfig("External video - 1:4 size", state = "normal")

        self.mode.set(1)
        self.change_mode()

        self.update_layout()

        self.update_image(0)

    def exportFireballData(self, no_background=False):
        """ Export LOG_SORT.INF file from FTPdetectinfo for fireball analysis.

        no_background: images will be built without background stars
        """
        if self.current_image == '':
            return None

        if (self.mode.get() == 3) or (self.mode.get() == 2 and self.data_type.get() == 2):
            # Only in confirmation in CAMS and Detected in Skypatrol

            save_path, image_list = self.fireball_deinterlacing_process(logsort_export = True, no_background = no_background)

            if save_path == '':
                return False

            if exportLogsort.exportLogsort(self.dir_path, save_path, self.data_type.get(), self.current_image, self.meteor_no, self.start_frame.get(), self.end_frame.get(), self.fps.get(), image_list) is False:
                tkMessageBox.showerror("Logsort export error", "Required files (FTPdetectinfo, CapturedStats or logfile.txt) were not found in the given folder!")

        else:
            pass
            # In detected or captured mode
            # GENERIC LOGSORT!
            generic_choice = tkMessageBox.askyesno("Generic LOG_SORT.INF", "Are you sure you want to create a generic LOG_SORT.INF file? \nSwitch to Confirmation mode for CAMS or Detected mode for Skypatrol to create a detection-based LOG_SORT.INF.")
            if generic_choice == 'yes':
                # Make generic
                pass
            return False

        tkMessageBox.showinfo("Fireball data", "Exporting fireball data done!")
        self.status_bar.config(text = "Exporting fireball data done!")

        return True

    def postprocessLogsort(self):
        """ Fixes logsort after analysis with CMN_FBA.
        """

        logsort_path = tkFileDialog.askopenfilename(initialdir = self.dir_path, parent = self.parent, title = "Choose LOG_SORT.INF to postprocess", initialfile = "LOG_SORT.INF", defaultextension = ".INF", filetypes = [('INF files', '.inf')])

        if logsort_path == '':
            return False

        if exportLogsort.postAnalysisFix(logsort_path, self.data_type.get()) is False:
            tkMessageBox.showerror("LOG_SORT.INF error", "LOG_SORT.INF could not be opened or no CaptureStats file was found in folder! If you are working with Skypatrol data, try changing Data type to 'Skypatrol'.")
        else:
            tkMessageBox.showinfo("LOG_SORT.INF", "Postprocessing LOG_SORT.INF done!")

    def show_about(self):
        tkMessageBox.showinfo("About",
            """CMN_binViewer version: """ + str(version) + """\n
            Croatian Meteor Network\n
            http://cmn.rgn.hr/\n
            Copyright © 2016 Denis Vida
            E-mail: denis.vida@gmail.com\n
Reading FF*.bin files: based on Matlab scripts by Peter S. Gural
gifsicle: Copyright © 1997-2013 Eddie Kohler
""")

    def show_key_bindings(self):
        tkMessageBox.showinfo("Key bindings",
            """Key Bindings:
            Changing images:
                - Arrow Down - move down by one image
                - Arrow Up - move up by one image
                - Home - jump to first image
                - End - jump to last image

            Changing mode:
                - Page Up - captured mode
                - Page Down - detected mode

            Changing filters:
                - Arrow Right - move right by one filter
                - Arrow Left - move left by one filter
                - F1 - maxframe
                - F2 - colorized
                - F3 - detection only
                - F4 - avgframe
                - F5 - odd filter set
                - F6 - even filter set and toggle with odd frame
                - F7 - show individual frames (use slider)

                - F9 - show video

            Sorting files:
                - Enter - copy FF*.bin to sorted folder

            Other:
                - Delete - toggle Deinterlace
                - Insert - toggle Hold levels
                """)

    def onExit(self):
        self.quit()
        self.destroy()
        sys.exit()

    def initUI(self):
        """ Initialize GUI elements.
        """

        self.parent.title("CMN_binViewer")

        # Configure the style of each element
        s = Style()
        s.configure("TButton", padding=(0, 5, 0, 5), font='serif 10', background = global_bg)
        s.configure('TLabelframe.Label', foreground =global_fg, background=global_bg)
        s.configure('TLabelframe', foreground =global_fg, background=global_bg, padding=(3, 3, 3, 3))
        s.configure("TRadiobutton", foreground = global_fg, background = global_bg)
        s.configure("TLabel", foreground = global_fg, background = global_bg)
        s.configure("TCheckbutton", foreground = global_fg, background = global_bg)
        s.configure("Vertical.TScrollbar", background=global_bg, troughcolor = global_bg)

        self.columnconfigure(0, pad=3)
        self.columnconfigure(1, pad=3)
        self.columnconfigure(2, pad=3)
        self.columnconfigure(3, pad=3)
        self.columnconfigure(4, pad=3)
        self.columnconfigure(5, pad=3)
        self.columnconfigure(6, pad=3)
        self.columnconfigure(7, pad=3)
        self.columnconfigure(8, pad=3)

        self.rowconfigure(0, pad=3)
        self.rowconfigure(1, pad=3)
        self.rowconfigure(2, pad=3)
        self.rowconfigure(3, pad=3)
        self.rowconfigure(4, pad=3)
        self.rowconfigure(5, pad=3)
        self.rowconfigure(6, pad=3)
        self.rowconfigure(7, pad=3)
        self.rowconfigure(8, pad=3)
        self.rowconfigure(9, pad=3)
        self.rowconfigure(10, pad=3)

        # MENUS

        # Make menu
        self.menuBar = Menu(self.parent)
        self.parent.config(menu=self.menuBar)

        # File menu
        fileMenu = Menu(self.menuBar, tearoff=0)
        fileMenu.add_command(label = "Open FF* folder", command = self.askdirectory)

        fileMenu.add_separator()
        fileMenu.add_command(label="Exit", command=quitBinviewer)
        # fileMenu.add_separator()

        # fileMenu.add_command(label="Exit", underline=0, command=self.onExit)
        self.menuBar.add_cascade(label="File", underline=0, menu=fileMenu)

        # Data type menu
        datatypeMenu = Menu(self.menuBar, tearoff = 0)
        datatypeMenu.add_checkbutton(label = "Auto", onvalue = 0, variable = self.data_type_var, command = self.update_data_type)
        datatypeMenu.add_separator()
        datatypeMenu.add_checkbutton(label = "CAMS", onvalue = 1, variable = self.data_type_var, command = self.update_data_type)
        datatypeMenu.add_checkbutton(label = "Skypatrol", onvalue = 2, variable = self.data_type_var, command = self.update_data_type)
        datatypeMenu.add_checkbutton(label = "RMS", onvalue = 3, variable = self.data_type_var, command = self.update_data_type)
        self.menuBar.add_cascade(label = "Data type", underline = 0, menu = datatypeMenu)

        # Confirmation menu
        self.confirmationMenu = Menu(self.menuBar, tearoff = 0)
        self.confirmationMenu.add_command(label = "Start", underline = 0, command = self.confirmationStart)
        self.confirmationMenu.add_command(label = "End", underline = 0, command = self.confirmationEnd)
        self.confirmationMenu.entryconfig("End", state = "disabled")
        self.confirmationMenu.add_separator()
        self.confirmationMenu.add_checkbutton(label = "Edge markers", onvalue = 1, variable = self.edge_marker, command = self.update_layout)
        self.confirmationMenu.add_checkbutton(label = "Meteor guidelines (external video)", onvalue = 1, variable = self.external_guidelines, command = self.update_layout)
        self.confirmationMenu.add_separator()
        self.confirmationMenu.add_checkbutton(label = "Detection centered video", onvalue = 0, variable = self.externalVideoOn, command = self.update_layout)
        self.confirmationMenu.add_checkbutton(label = "External video - 1:1 size", onvalue = 1, variable = self.externalVideoOn, command = self.update_layout)
        self.confirmationMenu.add_checkbutton(label = "External video - 1:1.5 size", onvalue = 2, variable = self.externalVideoOn, command = self.update_layout)
        self.confirmationMenu.add_checkbutton(label = "External video - 1:2 size", onvalue = 3, variable = self.externalVideoOn, command = self.update_layout)
        self.confirmationMenu.add_checkbutton(label = "External video - 1:4 size", onvalue = 4, variable = self.externalVideoOn, command = self.update_layout)
        self.menuBar.add_cascade(label = "Confirmation", underline = 0, menu = self.confirmationMenu)

        # Process Menu
        processMenu = Menu(self.menuBar, tearoff = 0)
        processMenu.add_command(label = "Make master dark frame", command = self.make_master_dark)
        processMenu.add_command(label = "Make master flat frame", command = self.make_master_flat)
        self.menuBar.add_cascade(label="Process", underline=0, menu=processMenu)

        # Fireball menu
        self.fireballMenu = Menu(self.menuBar, tearoff = 0)
        self.fireballMenu.add_command(label = "Export detection with background stars", command = lambda: self.exportFireballData(no_background = False))
        self.fireballMenu.add_command(label = "Export detection without background stars", command = lambda: self.exportFireballData(no_background = True))
        self.fireballMenu.add_separator()
        self.fireballMenu.add_command(label = "Postprocess LOG_SORT.INF", command = self.postprocessLogsort)
        self.menuBar.add_cascade(label="Fireball", underline=0, menu=self.fireballMenu)

        # Layout menu
        layoutMenu = Menu(self.menuBar, tearoff = 0)
        layoutMenu.add_checkbutton(label = "Vertical layout", onvalue = True, offvalue = False, variable = self.layout_vertical, command = self.update_layout)
        layoutMenu.add_checkbutton(label = "Horizontal layout", onvalue = False, offvalue = True, variable = self.layout_vertical, command = self.update_layout)
        self.menuBar.add_cascade(label = "Layout", menu = layoutMenu)

        # Resize menu
        resizeMenu = Menu(self.menuBar, tearoff = 0)
        resizeMenu.add_checkbutton(label = "Image size 1x", onvalue = 1, variable = self.image_resize_factor, command = self.update_layout)
        resizeMenu.add_checkbutton(label = "Image size 1/2x", onvalue = 2, variable = self.image_resize_factor, command = self.update_layout)
        resizeMenu.add_checkbutton(label = "Image size 1/4x", onvalue = 4, variable = self.image_resize_factor, command = self.update_layout)
        self.menuBar.add_cascade(label = "Resize", menu = resizeMenu)

        # Window menu
        self.windowMenu = Menu(self.menuBar, tearoff = 0)
        self.windowMenu.add_checkbutton(label = "Save image", onvalue = True, offvalue = False, variable = self.save_image_frame, command = self.update_layout)
        self.windowMenu.add_checkbutton(label = "Image levels", onvalue = True, offvalue = False, variable = self.image_levels_frame, command = self.update_layout)
        self.windowMenu.add_checkbutton(label = "Save animation", onvalue = True, offvalue = False, variable = self.save_animation_frame, command = self.update_layout)
        self.menuBar.add_cascade(label = "Window", menu = self.windowMenu)

        # Help Menu
        helpMenu = Menu(self.menuBar, tearoff=0)
        helpMenu.add_command(label = "Key bindings", command = self.show_key_bindings)
        helpMenu.add_command(label = "About", command = self.show_about)
        self.menuBar.add_cascade(label = "Help", underline=0, menu=helpMenu)

        # GUI SEGMENTS

        # Panel for mode
        mode_panel = LabelFrame(self, text=' Mode ')
        mode_panel.grid(row = 1, columnspan = 2, sticky='WE')

        self.captured_btn = Radiobutton(mode_panel, text="Captured", variable = self.mode, value = 1, command = self.change_mode)
        self.mode.set(1)
        self.detected_btn = Radiobutton(mode_panel, text="Detected", variable = self.mode, value = 2, command = self.change_mode)

        self.captured_btn.grid(row = 2, column = 0, padx=5, pady=2)
        self.detected_btn.grid(row = 2, column = 1, padx=5, pady=2)

        min_frames_label = Label(mode_panel, text = "Min. frames (0 - 255): ")
        min_frames_label.grid(row = 3, column = 0)

        self.min_frames_entry = ConstrainedEntry(mode_panel, textvariable = self.minimum_frames, width = 5)
        self.min_frames_entry.grid(row = 3, column = 1, sticky = "W")
        self.min_frames_entry.config(state = DISABLED)

        # Calibration & image features

        calib_panel = LabelFrame(self, text=' Calibration & image features ')
        calib_panel.grid(row = 3, column = 0, columnspan = 2, rowspan = 1, sticky = "NWE")

        self.dark_chk = Checkbutton(calib_panel, text = "Dark frame", variable = self.dark_status, command = lambda: self.update_image(0))
        self.dark_chk.grid(row = 4, column = 0, sticky = "W")

        dark_entry = StyledEntry(calib_panel, textvariable = self.dark_name, width = 25)
        dark_entry.grid(row = 4, column = 1, columnspan = 2, sticky = "W")

        dark_button = StyledButton(calib_panel, text = "Open", command = self.open_dark_path, width = 5)
        dark_button.grid(row =4, column = 3, sticky ="W")

        self.flat_chk = Checkbutton(calib_panel, text = "Flat frame", variable = self.flat_status, command = lambda: self.update_image(0))
        self.flat_chk.grid(row = 5, column = 0, sticky = "W")

        flat_entry = StyledEntry(calib_panel, textvariable = self.flat_name, width = 25)
        flat_entry.grid(row = 5, column = 1, columnspan = 2, sticky = "W")

        flat_button = StyledButton(calib_panel, text = "Open", command = self.open_flat_path, width = 5)
        flat_button.grid(row = 5, column = 3, sticky ="W")

        self.deinterlace_chk = Checkbutton(calib_panel, text = "Deinterlace", variable = self.deinterlace, command = lambda: self.update_image(0))
        self.deinterlace_chk.grid(row = 6, column = 0, sticky = "W")

        self.hold_levels_chk = Checkbutton(calib_panel, text = 'Hold levels', variable = self.hold_levels)
        self.hold_levels_chk.grid(row = 6, column = 1, sticky = "W")

        self.arcsinh_chk = Checkbutton(calib_panel, text = 'Enh. stars', variable = self.arcsinh_status, command = lambda: self.update_image(0))
        self.arcsinh_chk.grid(row = 6, column = 2, sticky = "W")

        self.invert_chk = Checkbutton(calib_panel, text = "Invert", variable = self.invert, command = lambda: self.update_image(0))
        self.invert_chk.grid(row = 6, column = 3, sticky = "W")

        # Listbox
        self.scrollbar = Scrollbar(self)
        self.listbox = Listbox(self, width = 47, yscrollcommand=self.scrollbar.set, exportselection=0, activestyle = "none", bg = global_bg, fg = global_fg)
        # Listbox position is set in update_layout function

        self.listbox.bind('<<ListboxSelect>>', self.update_image)
        self.scrollbar.config(command = self.listbox.yview)

        # Filters panel
        filter_panel = LabelFrame(self, text=' Filters ')
        filter_panel.grid(row = 1, column = 3, sticky = "W", padx=5, pady=5, ipadx=5, ipady=5, columnspan = 2)

        self.maxpixel_btn = Radiobutton(filter_panel, text = "Maxpixel", variable = self.filter, value = 1, command = lambda: self.update_image(0))
        self.maxpixel_btn.grid(row = 2, column = 3)
        self.filter.set(1)
        self.colored_btn = Radiobutton(filter_panel, text = "Colorized", variable = self.filter, value = 2, command = lambda: self.update_image(0))
        self.colored_btn.grid(row = 2, column = 4)
        self.detection_btn = Radiobutton(filter_panel, text = "Detection", variable = self.filter, value = 3, command = lambda: self.update_image(0))
        self.detection_btn.grid(row = 2, column = 5)
        self.avgpixel_btn = Radiobutton(filter_panel, text = "Avgpixel", variable = self.filter, value = 4, command = lambda: self.update_image(0))
        self.avgpixel_btn.grid(row = 2, column = 6)
        self.odd_btn = Radiobutton(filter_panel, text = "Odd", variable = self.filter, value = 5, command = lambda: self.update_image(0))
        self.odd_btn.grid(row = 2, column = 7)
        self.even_btn = Radiobutton(filter_panel, text = "Even", variable = self.filter, value = 6, command = lambda: self.update_image(0))
        self.even_btn.grid(row = 2, column = 8)

        # Frames
        self.frames_btn = Radiobutton(filter_panel, text = "Frames", variable = self.filter, value = 7, command = lambda: self.update_image(0))
        self.frames_btn.grid(row = 2, column = 9)

        # Video
        if not disable_UI_video:
            self.video_btn = Radiobutton(filter_panel, text = "Video", variable = self.filter, value = 10, command = lambda: self.update_image(0))
            self.video_btn.grid(row = 2, column = 10)

        # Sort panel
        sort_panel = LabelFrame(self, text=' Sort FF*.bins ')
        sort_panel.grid(row = 1, column = 5, sticky = "W", padx=2, pady=5, ipadx=5, ipady=5)

        sort_folder_label = Label(sort_panel, text = "Folder:")
        sort_folder_label.grid(row = 2, column = 4, sticky = "W")
        sort_folder_entry = StyledEntry(sort_panel, textvariable = self.sort_folder_path, width = 15)
        sort_folder_entry.grid(row = 3, column = 4)

        # previous_button = StyledButton(sort_panel, text ="<", width=3, command = lambda: self.move_img_up(0))
        # previous_button.grid(row = 2, column = 6, rowspan = 2)

        copy_button = StyledButton(sort_panel, text ="Copy", width=5, command = lambda: self.copy_bin_to_sorted(0))
        copy_button.grid(row = 2, column = 7, rowspan = 2)
        open_button = StyledButton(sort_panel, text ="Show folder", command = lambda: self.open_current_folder(0))
        open_button.grid(row = 2, column = 8, rowspan = 2)

        # next_button = StyledButton(sort_panel, text =">", width=3, command = lambda: self.move_img_down(0))
        # next_button.grid(row = 2, column = 9, rowspan = 2)

        # IMAGE
        try:
            # Show the TV test card image on program start
            noimage_data = open('noimage.bin', 'rb').read()
            noimage = PhotoImage(data = noimage_data)
        except:
            noimage = None

        self.imagelabel = Label(self, image = noimage)
        self.imagelabel.image = noimage
        self.imagelabel.grid(row=3, column=3, rowspan = 4, columnspan = 3)

        # Timestamp label
        # self.timestamp_label = Label(self, text = "YYYY-MM-DD HH:MM.SS.mms  FFF", font=("Courier", 12))
        self.timestamp_label = Label(self, text = "YYYY-MM-DD HH:MM.SS.mms", font=("Courier", 12))
        self.timestamp_label.grid(row = 7, column = 5, sticky = "E")
        # self.timestamp_label.grid(row = 2, column = 3, sticky = "WNS")

        # Save buttons
        self.save_panel = LabelFrame(self, text=' Save image ')  # Position set in update layout

        save_label = Label(self.save_panel, text = "Save")
        save_label.grid(row = 9, column = 3, sticky = "W")

        save_label = Label(self.save_panel, text = "Save as...")
        save_label.grid(row = 10, column = 3, sticky = "W")

        save_bmp = StyledButton(self.save_panel, text="BMP", width = 5, command = lambda: self.save_image(extension = 'bmp', save_as = False))
        save_bmp.grid(row = 9, column = 4)

        save_jpg = StyledButton(self.save_panel, text="JPG", width = 5, command = lambda: self.save_image(extension = 'jpg', save_as = False))
        save_jpg.grid(row = 9, column = 5)

        save_as_bmp = StyledButton(self.save_panel, text="BMP", width = 5, command = lambda: self.save_image(extension = 'bmp', save_as = True))
        save_as_bmp.grid(row = 10, column = 4)

        save_as_jpg = StyledButton(self.save_panel, text="JPG", width = 5, command = lambda: self.save_image(extension = 'jpg', save_as = True))
        save_as_jpg.grid(row = 10, column = 5)

        self.print_name_btn = Checkbutton(self.save_panel, text = "Embed name", variable = self.print_name_status)  # Position set in update_label

        # Levels adjustment
        self.levels_label = LabelFrame(self, text =" Image levels ")
        # Position set in update_layout function

        self.min_lvl_scale = Scale(self.levels_label, orient = "horizontal", width = 12, borderwidth = 0, background = global_bg, foreground = global_fg, highlightthickness = 0, sliderlength = 10, resolution = 2)
        self.min_lvl_scale.grid(row = 9, column = 4, sticky = "W")

        self.max_lvl_scale = Scale(self.levels_label, orient = "horizontal", width = 12, borderwidth = 0, background = global_bg, foreground = global_fg, highlightthickness = 0, to = 255, sliderlength = 10, resolution = 2)
        self.max_lvl_scale.grid(row = 9, column = 5, sticky = "W")

        self.gamma_scale = Scale(self.levels_label, orient = "horizontal", width = 12, borderwidth = 0, background = global_bg, foreground = global_fg, highlightthickness = 0, sliderlength = 20, from_ = -1.0, to = 1.0, resolution = 0.01, length = 100, showvalue = 0)
        self.gamma_scale.grid(row = 10, column = 4, columnspan = 2, sticky ="WE")
        self.gamma_scale.set(0)

        self.min_lvl_scale.set(0)
        self.min_lvl_scale.config(command = self.update_scales)

        self.max_lvl_scale.set(255)
        self.max_lvl_scale.config(command = self.update_scales)

        self.gamma_scale.config(command = self.update_scales)

        self.hold_levels_chk_horizontal = Checkbutton(self.levels_label, text = 'Hold levels', variable = self.hold_levels)
        # Position set in update_layout function

        # Animation panel
        self.animation_panel = LabelFrame(self, text=' Save animation ')
        # Position set in update_layout function

        start_frame_label = Label(self.animation_panel, text = "Start Frame: ")
        start_frame_label.grid(row = 9, column = 4, sticky = "W")
        self.start_frame_entry = ConstrainedEntry(self.animation_panel, textvariable = self.start_frame, width = 5)
        self.start_frame_entry.grid(row = 9, column = 5)

        end_frame_label = Label(self.animation_panel, text = "End Frame: ")
        end_frame_label.grid(row = 10, column = 4, sticky = "W")
        self.end_frame_entry = ConstrainedEntry(self.animation_panel, textvariable = self.end_frame, width = 5)
        self.end_frame_entry.grid(row = 10, column = 5)

        fps_label = Label(self.animation_panel, text ="FPS: ")
        fps_label.grid(row = 11, column = 4, rowspan = 2, sticky = "WE")

        fps_entry = ConstrainedEntry(self.animation_panel, textvariable = self.fps, width = 4)
        fps_entry.grid(row = 11, column = 5, rowspan = 2, sticky = "WE")

        gif_embed_btn = Checkbutton(self.animation_panel, text = "Embed name", variable = self.gif_embed)
        gif_embed_btn.grid(row = 9, column = 6, sticky = "W")

        repeatbtn = Checkbutton(self.animation_panel, text = "Repeat", variable = self.repeat)
        repeatbtn.grid(row = 10, column = 6, sticky = "W")

        perfield_btn = Checkbutton(self.animation_panel, text = "Per field", variable = self.perfield_var)
        perfield_btn.grid(row = 11, column = 6, sticky = "W")

        self.gif_make_btn = StyledButton(self.animation_panel, text ="GIF", command = self.make_gif, width = 10)
        # Position set in update_layout function

        # Frame slider
        self.frames_slider_panel = LabelFrame(self, text=' Frame ')
        # Position set in update_layout function

        self.frame_scale = Scale(self.frames_slider_panel, orient = "horizontal", width = 12, borderwidth = 0, background = global_bg, foreground = global_fg, highlightthickness = 0, sliderlength = 20, from_ = 0, to = 255, resolution = 1, length = 100)
        self.frame_scale.grid(row = 1, column = 1, columnspan = 5, sticky ="WE")
        self.frame_scale.config(command = self.update_image)

        frame_start_frame_label = Label(self.frames_slider_panel, text = "Start: ")
        frame_start_frame_label.grid(row = 2, column = 1, sticky = "W")
        self.frame_start_frame_entry = ConstrainedEntry(self.frames_slider_panel, textvariable = self.start_frame, width = 5)
        self.frame_start_frame_entry.grid(row = 2, column = 2)

        frame_end_frame_label = Label(self.frames_slider_panel, text = "End: ")
        frame_end_frame_label.grid(row = 2, column = 3, sticky = "W")
        self.frame_end_frame_entry = ConstrainedEntry(self.frames_slider_panel, textvariable = self.end_frame, width = 5)
        self.frame_end_frame_entry.grid(row = 2, column = 4)

        save_frames_btn = StyledButton(self.frames_slider_panel, text = "Save frames", command = self.fireball_deinterlacing_process)
        save_frames_btn.grid(row = 2, column = 5)

        # Status bar
        self.status_bar = Label(self, text="Start", relief="sunken", anchor="w")
        self.status_bar.grid(row = 11, column = 0, columnspan = 15, sticky = "WE")

        self.update_layout()


def log_timestamp():
    """ Returns timestamp for logging.
    """
    return datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')


class Catcher:
    """ Used for catching unhandled exceptions.
    """
    def __init__(self, func, subst, widget):
        self.func = func
        self.subst = subst
        self.widget = widget

    def __call__(self, *args):
        try:
            if self.subst:
                # args = apply(self.subst, args)
                args = self.subst(*args)  # python3
            # return apply(self.func, args)
            return self.func(*args)
        except SystemExit as msg:
            raise SystemExit(msg)
        except:
            log.critical(traceback.format_exc())
            tkMessageBox.showerror("Unhandled exception", "An unhandled exception has occured!\nPlease see the last logfile in the " + log_directory + " for more information!")
            sys.exit()


# Confirmation video global variables
confirmation_video_app = None
confirmation_video_root = None
stop_confirmation_video = False

# External video global variables
external_video_app = None
external_video_root = None
stop_external_video = False


def confirmationVideoInitialize(img_cols):
    """ Initializes the Confirmation video window.
    """

    global confirmation_video_app, confirmation_video_root

    confirmation_video_root = tk.Toplevel()
    confirmation_video_root.wm_attributes("-topmost", 1)  # Always on top

    # Set position of the external window
    img_cols = str(int(770 + 0.92 * img_cols / 2))
    confirmation_video_root.geometry('+' + img_cols + '+130')

    # Try window mondifications (works only on Windows!)
    try:
        # Remove minimize and maximize buttons
        confirmation_video_root.attributes("-toolwindow", 1)

        # Override close button to do nothing
        confirmation_video_root.protocol('WM_DELETE_WINDOW', lambda *args: None)

    except:
        pass


def externalVideoInitialize(img_cols):
    """ Initializes the External video window.
    """

    global external_video_app, external_video_root

    external_video_root = tk.Toplevel()
    external_video_root.wm_attributes("-topmost", 1)  # Always on top

    # Set position of the external window
    img_cols = str(int(770 + 0.92 * img_cols / 2))
    external_video_root.geometry('+' + img_cols + '+130')

    external_video_root.protocol('WM_DELETE_WINDOW', lambda *args: None)  # Override close button to do nothing
    external_video_root.attributes("-toolwindow", 1)  # Remove minimize and maximize buttons


def quitBinviewer():
    """ Cleanly exits binviewer. """

    root.quit()
    root.destroy()
    sys.exit()


if __name__ == '__main__':

    # Init argument parser
    parser = argparse.ArgumentParser()

    # Add the directory path argument
    parser.add_argument("dir_path", help="Directory to open.", nargs='?')

    # Add confirmation argument
    parser.add_argument("-c", "--confirmation", action="store_true", help="Run program in confirmation mode right away.")

    args = parser.parse_args()

    # Catch unhandled exceptions in Tkinter
    tk.CallWrapper = Catcher

    # Initialize logging, store logfile in AppData
    # For Windows
    if sys.platform == 'win32':
        log_directory = os.path.join(os.getenv('APPDATA'), log_directory)
    else:
        # For Unix
        log_directory = os.path.expanduser(os.path.join("~", "." + log_directory))

    mkdir_p(log_directory)
    log = logging.getLogger(__name__)
    log.setLevel(logging.INFO)

    log_file = os.path.join(log_directory, log_timestamp() + '.log')
    handler = logging.handlers.TimedRotatingFileHandler(log_file, when='D', interval=1)  # Log to a different file each day
    handler.setLevel(logging.INFO)

    formatter = logging.Formatter(fmt='%(asctime)s-%(levelname)s-%(module)s-line:%(lineno)d - %(message)s', datefmt='%Y/%m/%d %H:%M:%S')
    handler.setFormatter(formatter)
    log.addHandler(handler)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter(fmt='%(asctime)s-%(levelname)s: %(message)s', datefmt='%Y/%m/%d %H:%M:%S')
    ch.setFormatter(formatter)
    log.addHandler(ch)

    # Log program start
    log.info("Program start")
    log.info("Version: " + str(version))

    # Initialize main window
    root = tk.Tk()
    # Set window position and size

    if sys.platform == 'win32':
        root.wm_state('zoomed')
    else:
        root.geometry('+0+0')

    # Add a special function which controls what happens when when the close button is pressed
    root.protocol('WM_DELETE_WINDOW', quitBinviewer)

    # Set window icon
    try:
        root.iconbitmap(os.path.join('.', 'icon.ico'))
    except:
        pass

    # Init the BinViewer UI
    app = BinViewer(root, dir_path=args.dir_path, confirmation=args.confirmation)
    root.mainloop()
