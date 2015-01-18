#!/usr/bin/python
# -*- coding: utf-8 -*-

""" CMN binViewer
Croatian Meteor Network

Author: Denis Vida, 2014.
"""

version = 2.14

import os
import sys
import errno
import glob
import time
import datetime
import wx
import tkFileDialog
import tkMessageBox
import threading
import logging
import logging.handlers
import traceback
import numpy as np
from shutil import copy2
from Tkinter import Tk, W, E, IntVar, BooleanVar, StringVar, DoubleVar, Frame, ACTIVE, END, Listbox, Menu, PhotoImage, NORMAL, DISABLED, Entry, Scale, Button
import Tkinter as tk
from ttk import Label, Style, LabelFrame, Checkbutton, Radiobutton, Scrollbar
from PIL import Image as img
from PIL import ImageTk
from FF_bin_suite import readFF, buildFF, colorize_maxframe, max_nomean, load_dark, load_flat, process_array, saveImage, make_flat_frame, makeGIF, get_detection_only, get_processed_frames, adjust_levels, get_FTPdetect_coordinates, markDetections, deinterlace_array_odd, deinterlace_array_even
from confirmationClass import Confirmation

global_bg = "Black"
global_fg = "Gray"

config_file = 'config.ini'

log_directory = 'logs'

lock = threading.Lock()

def mkdir_p(path):
    """ Makes a directory and handles all errors"""
    try:
        os.makedirs(path)
    except OSError, exc:
        if exc.errno == errno.EEXIST:
            pass
        else: raise


class StyledButton(Button):
    """ Button with style """
    def __init__(self, *args, **kwargs):
        Button.__init__(self, *args, **kwargs)

        self.configure(foreground = global_fg, background = global_bg, borderwidth = 3)

class StyledEntry(Entry):
    """ Entry box with style """
    def __init__(self, *args, **kwargs):
        Entry.__init__(self, *args, **kwargs)

        self.configure(foreground = global_fg, background = global_bg, insertbackground = global_fg, disabledbackground = global_bg, disabledforeground = "DimGray")


class ConstrainedEntry(StyledEntry):
    """ Entry box with constrained values which can be input (e.g. 0-255)"""
    def __init__(self, *args, **kwargs):
        StyledEntry.__init__(self, *args, **kwargs)
        self.maxvalue = 255
        vcmd = (self.register(self.on_validate),"%P")
        self.configure(validate="key", validatecommand=vcmd)
        #self.configure(foreground = global_fg, background = global_bg, insertbackground = global_fg)

    def disallow(self):
        self.bell()

    def update_value(self, maxvalue):
        self.maxvalue = maxvalue
        vcmd = (self.register(self.on_validate),"%P")
        self.configure(validate="key", validatecommand=vcmd)

    def on_validate(self, new_value):
        try:
            if new_value.strip() == "": return True
            value = int(new_value)
            if value < 0 or value > self.maxvalue:
                self.disallow()
                return False
        except ValueError:
            self.disallow()
            return False

        return True

class Video(threading.Thread): 
        """ Class for handling video showing in another thread"""
        def __init__(self, viewer_class, img_path):
            super(Video, self).__init__()
            self.viewer_class = viewer_class #Set main binViewer class to be callable inside Video class
            self.img_path = img_path

            #global readFF
            #self.readFF_video = self.viewer_class.readFF_decorator(readFF) #Decorate readFF function by also passing datatype

        def run(self):
            
            temp_frame = self.viewer_class.temp_frame.get()
            end_frame = self.viewer_class.end_frame.get()
            start_frame = self.viewer_class.start_frame.get()

            starting_image = self.viewer_class.current_image

            video_cache = [] #Storing the fist run of reading from file to an array

            ff_bin_read = readFF(self.img_path, datatype = self.viewer_class.data_type.get())

            # Cache everything under 75 frames
            if (end_frame - start_frame + 1) <= 75:
                cache_flag = True
            else:
                cache_flag = False

            while self.viewer_class.stop_video.get() == False: #Repeat until video flag is set to stop

                start_time = time.clock() #Time the script below to achieve correct FPS

                if temp_frame>=end_frame:
                    self.viewer_class.temp_frame.set(start_frame)
                    temp_frame = start_frame
                else:
                    temp_frame += 1

                if cache_flag == True:
                    
                    ##Cache video files during first run
                    if len(video_cache) < (end_frame - start_frame + 1):
                        img_array = buildFF(ff_bin_read, temp_frame, videoFlag = True)
                        video_cache.append(img_array)
                    else:
                        img_array = video_cache[temp_frame - start_frame] #Read cached video frames in consecutive runs

                else:
                    img_array = buildFF(ff_bin_read, temp_frame, videoFlag = True)

                
                self.viewer_class.img_data = img_array

                #temp_image = ImageTk.PhotoImage(img.fromarray(img_array).convert("RGB")) #Prepare for showing
                temp_image = ImageTk.PhotoImage(img.fromarray(img_array)) #Prepare for showing

                lock.acquire()
                self.viewer_class.imagelabel.configure(image = temp_image) #Set image to image label
                self.viewer_class.imagelabel.image = temp_image
                lock.release()

                #Set timestamp
                self.viewer_class.set_timestamp(temp_frame)
                
                #Sleep for 1/FPS with corrected time for script running time
                end_time = time.clock()

                script_time = float(end_time - start_time)
                if not script_time > 1.0/self.viewer_class.fps.get(): #Don't run sleep if the script time is bigger than FPS
                    time.sleep(1.0/self.viewer_class.fps.get() - script_time)

class ConfirmationVideo(threading.Thread): 
        """ Class for handling Confirmation video showing in another thread"""
        def __init__(self, viewer_class, img_path, meteorNo, FTPdetectinfoContents, cropSize = 64):
            super(ConfirmationVideo, self).__init__()
            self.viewer_class = viewer_class #Set main binViewer class to be callable inside Video class
            self.img_path = img_path
            self.cropSize = cropSize

            lock.acquire()
            self.segmentList = get_FTPdetect_coordinates(FTPdetectinfoContents, self.viewer_class.current_image, meteorNo)
            lock.release()

            #global readFF
            #self.readFF_video = self.viewer_class.readFF_decorator(readFF) #Decorate readFF function by also passing datatype

        def run(self):
            
            #temp_frame = self.viewer_class.temp_frame.get()
            #end_frame = self.viewer_class.end_frame.get()
            #start_frame = self.viewer_class.start_frame.get()

            videoCache = [] #Storing the fist run of reading from file to an array

            ffBinRead = readFF(self.img_path, datatype = self.viewer_class.data_type.get())

            ncols = ffBinRead.ncols[0] - 1
            nrows = ffBinRead.nrows[0] - 1

            cropedList = []
            firstRun = True

            startFrame = 0
            endFrame = len(self.segmentList[0])-1
            tempFrame = startFrame

            #while self.viewer_class.stop_confirmation_video.get() == False: #Repeat until video flag is set to stop
            #for i in range (100):
            while 1:

            #for coordinate in self.segmentList[0]:
                #print coordinate
                if self.viewer_class.stop_confirmation_video.get() == True:
                    break

                start_time = time.clock() #Time the script below to achieve correct FPS

                if firstRun:

                    coordinate = self.segmentList[0][tempFrame]

                    frame, x, y = coordinate

                    x = int(round(x, 0))

                    # Make sure each center row is even
                    y = int(y)
                    if y % 2 == 1:
                        y += 1
                    
                    x_left = x - self.cropSize
                    y_left = y - self.cropSize

                    x_right = x + self.cropSize
                    y_right = y + self.cropSize

                    x_diff = 0
                    y_diff = 0
                    x_end = self.cropSize*2
                    y_end = self.cropSize*2

                    fillZeoresFlag = False
                    if x_left < 0:
                        fillZeoresFlag = True
                        x_diff = -x_left
                        x_end = self.cropSize*2

                        x_left = 0
                        

                    if y_left < 0:
                        fillZeoresFlag = True
                        y_diff = -y_left
                        y_end = self.cropSize*2

                        y_left = 0
                        

                    if x_right > ncols:
                        fillZeoresFlag = True
                        x_diff = 0
                        x_end = self.cropSize*2 - (x_right - ncols)

                        x_right = ncols
                        

                    if y_right > nrows:
                        fillZeoresFlag = True
                        y_diff = 0
                        y_end = self.cropSize*2 - (y_right - nrows - 1)

                        y_right = nrows + 1
                        

                    imageArray = buildFF(ffBinRead, int(frame), videoFlag = True)

                    # If croped area is in the corner, fill corner with zeroes
                    if fillZeoresFlag:

                        cropedArray = np.zeros(shape =(self.cropSize*2, self.cropSize*2))
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

                    videoCache.append(np.copy(cropedArray))

                    del imageArray
                    del x_left
                    del x_right
                    del y_left
                    del y_right

                else:

                    cropedArray = videoCache[tempFrame]

                lock.acquire()
                tempImage = ImageTk.PhotoImage(img.fromarray(cropedArray).resize((256, 256), img.ANTIALIAS)) #Prepare for showing
                try:
                    self.viewer_class.confirmationVideoLabel.configure(image = tempImage) #Set image to image label
                    self.viewer_class.confirmationVideoLabel.image = tempImage
                except:
                    print 'Error while showing confirmation image. Skipping to preserve program integrity.'
                lock.release()

                del cropedArray
                del tempImage
                
                #Sleep for 1/FPS with corrected time for script running time
                end_time = time.clock()

                script_time = float(end_time - start_time)
                slowFactor = 2
                if not script_time > slowFactor*1.0/self.viewer_class.fps.get(): #Don't run sleep if the script time is bigger than FPS
                    time.sleep(slowFactor*1.0/self.viewer_class.fps.get() - script_time) 
                    pass

                #Used for frame count, do NOT comment out!
                if tempFrame == endFrame:
                    tempFrame = startFrame
                    firstRun = False
                else:
                    tempFrame += 1



class BinViewer(Frame):

  
    def __init__(self, parent):
        """ Runs only when the viewer class is created (i.e. on the program startup only) """
        #parent.geometry("1366x768")
        Frame.__init__(self, parent, bg = global_bg)  
        parent.configure(bg = global_bg) #Set backgound color
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(0, weight=1)
        
        self.grid(sticky="NSEW") #Expand frame to all directions
        #self.grid_propagate(0)
         
        self.parent = parent


        #Define variables
        self.filter_no = 6 #Number of filters
        self.dir_path = os.path.abspath(os.sep)

        self.layout_vertical = BooleanVar() #Layout variable

        #Read configuration file
        config_content = self.read_config()

        self.dir_path = config_content[2]

        orientation = config_content[0]
        if orientation == 0:
            self.layout_vertical.set(False)
        else:
            self.layout_vertical.set(True)


        self.mode = IntVar()
        self.minimum_frames = IntVar()
        self.minimum_frames.set(0)

        self.detection_dict = {}

        self.data_type_var = IntVar() #For GUI
        self.data_type_var.set(0) #Set to Auto

        self.data_type = IntVar() #For backend
        self.data_type.set(1) #Set to CAMS

        self.filter = IntVar()
        self.old_filter = IntVar()
        self.img_data = 0
        self.current_image = ''
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

        self.hold_levels = BooleanVar()
        self.hold_levels.set(False)

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

        self.frame_slider_value = IntVar()
        self.frame_slider_value.set(0)

        self.starting_image = '' #Used for video
        self.stop_video = BooleanVar()
        self.stop_video.set(True)

        self.stop_confirmation_video = BooleanVar()
        self.stop_confirmation_video.set(True)

        #GIF
        self.gif_embed = BooleanVar()
        self.gif_embed.set(False)

        self.repeat = BooleanVar()
        self.repeat.set(True)

        self.perfield_var = BooleanVar()
        self.perfield_var.set(False)

        self.fps = IntVar()
        self.fps.set(config_content[1])

        #Levels
        self.gamma = DoubleVar()
        self.gamma.set(1.0)

        #Frames visibility
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

        # Confirmation
        self.reject_finish_flag = False

        # Misc
        global readFF
        readFF = self.readFF_decorator(readFF) #Decorate readFF function by also passing datatype, so that readFF doesn't have to be changed through the code

        # Initilize GUI
        self.initUI()

        # Bind key presses, window changes, etc. (key bindings)
        
        parent.bind("<Home>", self.move_top)
        parent.bind("<End>", self.move_bottom)
        parent.bind("<Up>", self.move_img_up)
        parent.bind("<Down>", self.move_img_down)

        parent.bind("<Prior>", self.captured_mode_set) #Page up
        parent.bind("<Next>", self.detected_mode_set) #Page up

        parent.bind("<Left>", self.filter_left)
        parent.bind("<Right>", self.filter_right)
        #parent.bind("<Key>", self.update_image)
        #parent.bind("<Button-1>", self.update_image)

        parent.bind("<F1>", self.maxframe_set)
        parent.bind("<F2>", self.colorized_set)
        parent.bind("<F3>", self.detection_only_set)
        parent.bind("<F4>", self.avgframe_set)

        parent.bind("<F5>", self.odd_set)
        parent.bind("<F6>", self.even_set_toggle)
        parent.bind("<F7>", self.frame_filter_set)

        parent.bind("<F9>", self.video_set)

        parent.bind("<Delete>", self.deinterlace_toggle)
        parent.bind("<Insert>", self.hold_levels_toggle)
        #parent.bind("<F2>", self.flat_toggle)
        #parent.bind("<F1>", self.dark_toggle)
        parent.bind("<Return>", self.copy_bin_to_sorted)

    def readFF_decorator(self, func):
        """ Decorator used to pass self.data_type to readFF without changing all readFF statements in the code """
        
        def inner(*args, **kwargs):
            if "datatype" in kwargs:
                return func(*args, **kwargs)
            else:
                return func(*args, datatype = self.data_type.get())
        
        return inner

    def correct_datafile_name(self, datafile):
        """ Returns True if the given string is a proper FF*.bin or Skypatrol name (depending on data type), else it returns false"""

        if self.data_type.get() == 1: #CAMS data type
            if len(datafile) == 37: #e.g. FF451_20140819_003718_000_0397568.bin
                if len([ch for ch in datafile if ch =="_"]) == 4:
                    if datafile.split('.')[-1] =='bin':
                        if datafile[0:2] =="FF":
                            return True
        
        else:  #Skypatrol data type
            if len(datafile) == 12: #e.g. 00000171.bmp
                if datafile.split('.')[-1] =='bmp':
                    return True

        return False

    def read_config(self):
        """ Reads the configuration file """

        orientation = 1
        fps = 25
        dir_path = self.dir_path

        read_list = (orientation, fps)

        try:
            config_lines = open(config_file).readlines()
        except:
            tkMessageBox.showerror("Configuration file "+config_file+" not found! Program files are compromised!")
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

        read_list = (orientation, fps, dir_path)

        return read_list

    def write_config(self):
        """ Writes the configuration file """
        orientation = int(self.layout_vertical.get())
        fps = int(self.fps.get())
        if not fps in (25, 30):
            fps = 25

        try:
            new_config = open(config_file, 'w')
        except:
            return False

        new_config.write("#Configuration file\n#DO NOT CHANGE VALUES MANUALLY\n\n")

        new_config.write("orientation = "+str(orientation)+" # 0 vertical, 1 horizontal\n")
        new_config.write("fps = "+str(fps)+"\n")
        if ('CAMS' in self.dir_path) or ('Captured' in self.dir_path) or ('Archived' in self.dir_path):
            temp_path = self.dir_path
            new_path = []
            for line in temp_path.split(os.sep):
                if ('Captured' in line) or ('Archived' in line):
                    new_path.append(line)
                    break
                new_path.append(line)

            temp_path = (os.sep).join(new_path)

            new_config.write("dir_path = "+temp_path.strip()+"\n")
        
        return True

    def update_data_type(self):
        """ Updates the data_type variable to match data type of directory content. If there are CAMS files, it returns 1, if the Skypatrol files prevail, it returns 2"""
        data_type_var = self.data_type_var.get()

        if data_type_var == 0:
            #Auto - determine data type
            bin_count = len(glob.glob1(self.dir_path,"*.bin"))
            bmp_count = len(glob.glob1(self.dir_path,"*.bmp"))

            dir_contents = os.listdir(self.dir_path)

            if bin_count >= bmp_count or ("FTPdetectinfo_" in dir_contents):
                self.data_type.set(1) #Set to CAMS if there are more bin files
                self.end_frame.set(255)
            else:
                self.data_type.set(2) #Set to Skypatrol if there are more BMP files
                self.end_frame.set(1500)

        elif data_type_var == 1:
            #CAMS
            self.data_type.set(1)
            self.end_frame.set(255)

        elif data_type_var == 2:
            #Skypatrol
            self.data_type.set(2)
            self.end_frame.set(1500)

        self.update_listbox(self.get_bin_list()) #Update listbox

        self.mode.set(1)
        self.filter.set(1)
        self.change_mode()
        self.move_top(0) #Move listbox cursor to the top

        self.update_image(0)


    def update_layout(self):
        """ Updates the layout (horizontal/vertical) """

        self.menuBar.entryconfig("Window", state = "normal")

        #List of adjustable frames
        layout_frames = [self.save_image_frame, self.image_levels_frame, self.save_animation_frame, self.frame_scale_frame]
        enabled_frames = 0
        for frame in layout_frames:
            if frame.get() == True:
                enabled_frames -= 1

        #First column of vertical layout
        start_column = 3 + 3

        if self.layout_vertical.get() == True:

            #Vertical
            if self.mode.get() == 3:
                # COnfirmation size, make room for confirmation video
                self.ff_list.config(height = 20) #Listbox size
                self.ff_list.grid(row = 6, column = 0, rowspan = 3, columnspan = 2, sticky = "S") # Listbox position
                self.confirmationVideoLabel.grid(row = 4, column = 0, rowspan = 2, columnspan = 2, sticky = "NSE") # Video position
                self.scrollbar.grid(row = 6, column = 2, rowspan = 3, sticky = "NS")
            else:
                self.confirmationVideoLabel.grid_forget()
                self.ff_list.config(height = 37) #Listbox size
                self.ff_list.grid(row = 4, column = 0, rowspan = 7, columnspan = 2, sticky = "NS") # Listbox position
                self.scrollbar.grid(row = 4, column = 2, rowspan = 7, sticky = "NS") # Scrollbar size

            self.hold_levels_chk_horizontal.grid_forget()
            self.hold_levels_chk.grid(row = 6, column = 1, sticky = "W", pady=5)

            #Check if Save image frame is enabled in Windows menu, if not, hide it
            if self.save_image_frame.get() == True:
                self.save_panel.grid(row = 8, column = start_column+enabled_frames, rowspan = 2, sticky = "NS", padx=2, pady=5, ipadx=3, ipady=3)
                enabled_frames += 1
                self.print_name_btn.grid(row = 9, column = 6, rowspan = 2)
            else:
                self.save_panel.grid_forget()

            #Check if Image levels frame is enabled in Windows menu, if not, hide it
            if self.image_levels_frame.get() == True:
                self.levels_label.grid(row = 8, column = start_column+enabled_frames, rowspan = 2, sticky = "NS", padx=2, pady=5, ipadx=3, ipady=3)
                enabled_frames += 1
            else:
                self.levels_label.grid_forget()

            #Check if Save animation frame is enabled in Windows menu, if not, hide it
            if self.save_animation_frame.get() == True:
                self.animation_panel.grid(row = 8, column = start_column+enabled_frames, rowspan = 2, columnspan = 1, sticky = "NS", padx=2, pady=5, ipadx=3, ipady=3)
                enabled_frames += 1
                self.gif_make_btn.grid(row = 9, column = 7, rowspan = 4, sticky = "NSEW")
            else:
                self.animation_panel.grid_forget()

            #Frame scale if filter "Frames" is chosen
            if self.frame_scale_frame.get() == True:
                self.frames_slider_panel.grid(row = 8, column = start_column+enabled_frames, rowspan = 2, sticky = "NS", padx=2, pady=5, ipadx=3, ipady=3)
                enabled_frames += 1
            else:
                self.frames_slider_panel.grid_forget()

        else:
            #Horizontal

            if self.mode.get() == 3:
                # COnfirmation size, make room for confirmation video
                self.ff_list.config(height = 12) #Listbox size
                self.ff_list.grid(row = 6, column = 0, rowspan = 3, columnspan = 2, sticky = "NS") # Listbox position
                self.confirmationVideoLabel.grid(row = 4, column = 0, rowspan = 2, columnspan = 2, sticky = "NSE") # Video position
                self.scrollbar.grid(row = 6, column = 2, rowspan = 3, sticky = "NS")
            else:
                self.confirmationVideoLabel.grid_forget()
                self.ff_list.config(height = 30) #Listbox size
                self.ff_list.grid(row = 4, column = 0, rowspan = 7, columnspan = 2, sticky = "NS") # Listbox position
                self.scrollbar.grid(row = 4, column = 2, rowspan = 7, sticky = "NS") # Scrollbar size

            self.menuBar.entryconfig("Window", state = "disabled")

            self.hold_levels_chk.grid_forget()
            self.hold_levels_chk_horizontal.grid(row = 11, column = 4, columnspan = 2, sticky = "W")


            self.save_panel.grid(row = 3, column = 6, rowspan = 1, sticky = "NEW", padx=2, pady=5, ipadx=3, ipady=3)
            self.print_name_btn.grid(row = 11, column = 3, rowspan = 1)

            self.animation_panel.grid(row = 4, column = 6, rowspan = 1, columnspan = 1, sticky = "NEW", padx=2, pady=5, ipadx=3, ipady=3)

            self.levels_label.config(width = 10)
            self.levels_label.grid(row = 5, column = 6, rowspan = 1, padx=2, pady=5, ipadx=3, ipady=3, sticky ="NEW")

            self.gif_make_btn.grid(row = 13, column = 4, rowspan = 2, columnspan = 2, sticky = "EW", padx=2, pady=5)

            self.frames_slider_panel.grid(row = 6, column = 6, rowspan = 1, padx=2, pady=5, ipadx=3, ipady=3, sticky ="NEW")

        self.write_config()
            

    def move_img_up(self, event):
        """ Moves one list entry up if the focus is not on the list, when the key Up is pressed"""
                
        if not self.ff_list is self.parent.focus_get():
            self.ff_list.focus()

            try:
                cur_index = int(self.ff_list.curselection()[0])
            except:
                return None
            next_index = cur_index - 1
            if next_index < 0:
                next_index = 0
            
            self.ff_list.activate(next_index)
            self.ff_list.selection_clear(0, END)
            self.ff_list.selection_set(next_index)
            self.ff_list.see(next_index)
            
            self.update_image(1)
        #print 'gore'

    def move_img_down(self, event):
        """ Moves one list entry down if the focus is not on the list, when the key Down is pressed"""
        if not self.ff_list is self.parent.focus_get():
            self.ff_list.focus()
            
            try:
                cur_index = int(self.ff_list.curselection()[0])
            except:
                return None
            next_index = cur_index + 1
            size = self.ff_list.size()-1
            if next_index > size:
                next_index = size
            
            self.ff_list.activate(next_index)
            self.ff_list.selection_clear(0, END)
            self.ff_list.selection_set(next_index)
            self.ff_list.see(next_index)

            self.update_image(1)
        #print 'dolje'

    def move_top(self, event):
        """ Moves to the top entry when Home key is pressed"""
        if not self.ff_list is self.parent.focus_get():
            self.ff_list.focus()

        self.ff_list.activate(0)
        self.ff_list.selection_clear(0, END)
        self.ff_list.selection_set(0)
        self.ff_list.see(0)

        self.update_image(0)

    def move_bottom(self, event):
        """ Moves to the last entry when End key is pressed"""
        if not self.ff_list is self.parent.focus_get():
            self.ff_list.focus()

        self.ff_list.activate(END)
        self.ff_list.selection_clear(0, END)
        self.ff_list.selection_set(END)
        self.ff_list.see(END)

        self.update_image(0)

    def move_index(self, index):
        """Moves the list cursor to given index"""

        if not self.ff_list is self.parent.focus_get():
            self.ff_list.focus()

        self.ff_list.activate(index)
        self.ff_list.selection_clear(0, END)
        self.ff_list.selection_set(index)
        self.ff_list.see(index)

        self.update_image(0)

    def captured_mode_set(self, event):
        """ Change mode to captured"""
        self.mode.set(1)
        self.change_mode()

    def detected_mode_set(self, event):
        """ Change mode to detected"""
        self.mode.set(2)
        self.change_mode()

    def maxframe_set(self, event):
        """ Set maxframe filter by pressing F1"""
        if self.mode.get() != 2: # Disabled in detections mode
            self.filter.set(1)
            self.update_image(0)

    def colorized_set(self, event):
        """ Set colored filter by pressing F2"""
        if self.mode.get() != 2: # Disabled in detections mode
            self.filter.set(2)
            self.update_image(0)

    def detection_only_set(self, event):
        """ Set odd frame filter by pressing F4"""
        self.filter.set(3)
        self.update_image(0)

    def avgframe_set(self, event):
        """ Set odd frame filter by pressing F3"""
        if self.mode.get() != 2: # Disabled in detections mode
            self.filter.set(4)
            self.update_image(0)

    def odd_set(self, event):
        """ Set odd frame filter by pressing F5"""
        if self.mode.get() != 2: # Disabled in detections mode
            self.filter.set(5)
            self.update_image(0)

    def even_set_toggle(self, event):
        """Set even frame filter by pressing F6, an toggle with odd frame by further pressing"""
        if self.mode.get() != 2: # Disabled in detections mode
            if self.filter.get() == 6:
                self.filter.set(5)
            else:
                self.filter.set(6)

            self.update_image(0)

    def frame_filter_set(self, event):
        """ Set Frame filter by pressing F7 """
        self.filter.set(7)
        self.update_image(0)

    def video_set(self, event):
        """ Sets VIDEO filter by pressing F9 """
        self.filter.set(10)
        self.update_image(0)

    def filter_left(self, event):
        """ Moves the filter field to the left"""
        if self.mode.get() != 2: # Disabled in detections mode
            next_filter = self.filter.get() - 1
            if next_filter<1 or next_filter>self.filter_no:
                next_filter = self.filter_no
            self.filter.set(next_filter)
        else: #In detected mode
            self.filter.set(3)

        self.update_image(0)

    def filter_right(self, event):
        """ Moves the filter field to the right"""
        if self.mode.get() != 2: # Disabled in detections mode
            next_filter = self.filter.get() + 1
            if next_filter>self.filter_no:
                next_filter = 1
            self.filter.set(next_filter)
        else: #In detected mode
            self.filter.set(3)

        self.update_image(0)

    def deinterlace_toggle(self, event):
        """ Turns the deinterlace on/off"""
        if self.deinterlace.get() == True:
            self.deinterlace.set(False)
        else:
            self.deinterlace.set(True)

        self.update_image(0)

    def hold_levels_toggle(self, event):
        """ Toggle Hold levels button """
        if self.hold_levels.get() == True:
            self.hold_levels.set(False)
        else:
            self.hold_levels.set(True)

    def dark_toggle(self, event):
        """Toggles the dark frame on/off"""
        if self.dark_status.get() == True:
            self.dark_status.set(False)
        else:
            self.dark_status.set(True)

        self.update_image(0)

    def open_dark_path(self):
        """ Opens dark frame via file dialog"""
        temp_dark = tkFileDialog.askopenfilename(initialdir = self.dir_path, parent = self.parent, title = "Choose dark frame file", initialfile = "dark.bmp", defaultextension = ".bmp", filetypes = [('BMP files', '.bmp')])
        temp_dark = temp_dark.replace('/', os.sep)
        if temp_dark != '':
            self.dark_name.set(temp_dark)

    def open_flat_path(self):
        """ Opens flat frame via file dialog"""
        temp_flat = tkFileDialog.askopenfilename(initialdir = self.dir_path, parent = self.parent, title = "Choose flat frame file", initialfile = "flat.bmp", defaultextension = ".bmp", filetypes = [('BMP files', '.bmp')])
        temp_flat = temp_flat.replace('/', os.sep)
        if temp_flat != '':
            self.flat_name.set(temp_flat)

    def flat_toggle(self, event):
        """Toggles the flat frame on/off"""
        if self.flat_status.get() == True:
            self.flat_status.set(False)
        else:
            self.flat_status.set(True)

        self.update_image(0)

    def update_current_image(self):
        """ Updates 2 varibales for tracking the current image, without changing the screen. Used for confirmation. """

        self.current_image = self.ff_list.get(self.ff_list.curselection()[0])
        self.confirmationListboxEntry = " ".join(self.current_image.split()[0:2])

        # Modify current image for Confirmation mode
        if self.mode.get() == 3: 
            self.current_image = self.current_image.split()[0]

    def update_image(self, event, update_levels = False):
        """ Updates the current image on the screen"""

        self.dir_path = self.dir_path.replace('/', os.sep)

        self.status_bar.config(text = "View image") #Update status bar
        try: #Check if the list is empty. If it is, do nothing.
            self.current_image = self.ff_list.get(self.ff_list.curselection()[0])
        except:
            return 0

        lock.acquire()
        self.stop_video.set(True) #Stop video every image update
        self.stop_confirmation_video.set(True)
        lock.release()
        
        try:
            self.video_thread.join() #Wait for the video thread to finish
            del self.video_thread #Delete video thread
        except:
            pass

        try:
            self.confirmation_video_thread.join()
            del self.confirmation_video_thread
        except:
            pass

        # Only on image change, set proper ConstrainedEntry maximum values for Video and Frame filter start and end frames
        if self.current_image != self.old_image:

            if self.data_type.get() == 1: #CAMS
                # Set constrained entry max values
                self.start_frame_entry.update_value(255)
                self.end_frame_entry.update_value(255)
                self.frame_start_frame_entry.update_value(255)
                self.frame_end_frame_entry.update_value(255)

            else: # Skypatrol
                # Set constrained entry max values
                self.start_frame_entry.update_value(1500)
                self.end_frame_entry.update_value(1500)
                self.frame_start_frame_entry.update_value(1500)
                self.frame_end_frame_entry.update_value(1500)


        if self.mode.get() == 1: #Prepare for Captured mode
            if event == 1: #Set only when the image is changed
                self.start_frame.set(0)
                if self.data_type.get() == 1: #CAMS
                    self.end_frame.set(255)
                    self.frame_scale.config(to = 255)

                else: # Skypatrol
                    self.end_frame.set(1500)
                    self.frame_scale.config(to = 1500)

        elif self.mode.get() == 2: #Detection mode preparations, find the right image and set the start and end frames into entry fields
            temp_img = self.detection_dict[self.current_image] #Get image data
            
            self.current_image = temp_img[0]
            start_frame = temp_img[1][0] #Set start frame
            end_frame = temp_img[1][1] #Set end frame

            start_temp = start_frame-5
            end_temp = end_frame+5

            start_temp = 0 if start_temp<0 else start_temp
            if self.data_type.get() == 1: #CAMS data type
                end_temp = 255 if end_temp>255 else end_temp
            else: #Skypatrol data dype
                end_temp = 1500 if end_temp>1500 else end_temp

            self.start_frame.set(start_temp)
            self.end_frame.set(end_temp)

        elif self.mode.get() == 3: # Prepare for confirmation

            self.confirmationListboxEntry = " ".join(self.current_image.split()[0:2])
            temp_info = self.confirmationDict[self.confirmationListboxEntry]

            # Change to Maxpixel filter after each image change
            if self.old_confirmation_image != self.current_image:
                self.filter.set(1)
                self.old_confirmation_image = self.current_image

            self.current_image, meteorNo = self.current_image.split()[0:2]

            # Start confirmation video
            if not self.filter.get() in (7, 10):
                start_frame = temp_info[1]
                end_frame = temp_info[2]

                self.start_frame.set(start_frame)
                self.end_frame.set(end_frame)

                img_path = self.dir_path+os.sep+self.current_image

                self.stop_confirmation_video.set(False) #Set "stop video" flag to False -> video will run
                self.confirmation_video_thread = ConfirmationVideo(app, img_path, int(meteorNo), self.ConfirmationInstance.FTPdetect_file_content)
                self.confirmation_video_thread.start() #Start video thread


        img_path = self.dir_path+os.sep+self.current_image

        if not os.path.isfile(img_path):
            tkMessageBox.showerror("File error", "File not found:\n"+img_path)
            return 0

        dark_frame = None
        flat_frame = None
        flat_frame_scalar = None

        # Do if the dark frame is on
        if self.dark_status.get() == True: 
            if not os.sep in self.dark_name.get():
                dark_path = self.dir_path+os.sep+self.dark_name.get()
            else:
                dark_path = self.dark_name.get()
            try:
                dark_frame = load_dark(dark_path)
            except:
                tkMessageBox.showerror("Dark frame file error", "Cannot find dark frame file: "+self.dark_name.get())
                self.dark_status.set(False)

        # Do if the flat frame is on
        if self.flat_status.get() == True: 
            if not os.sep in self.flat_name.get():
                flat_path = self.dir_path+os.sep+self.flat_name.get()
            else:
                flat_path = self.flat_name.get()
            try:
                flat_frame, flat_frame_scalar = load_flat(flat_path)
            except:
                tkMessageBox.showerror("Flat frame file error", "Cannot find flat frame file: "+self.flat_name.get())
                self.flat_status.set(False)

        

        # Make changes if the filter has changed
        if self.old_filter.get() != self.filter.get():
            # Set all butons to be active
            self.dark_chk.config(state = NORMAL) 
            self.flat_chk.config(state = NORMAL)
            self.deinterlace_chk.config(state = NORMAL)
            self.hold_levels_chk.config(state = NORMAL)
            self.max_lvl_scale.config(state = NORMAL)
            self.min_lvl_scale.config(state = NORMAL)
            self.gamma_scale.config(state = NORMAL)

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


        #Apply individual filters
        if self.filter.get() == 1: #Maxpixel
            img_array = process_array(readFF(img_path).maxpixel, flat_frame, flat_frame_scalar, dark_frame, self.deinterlace.get())
            self.img_name_type = 'maxpixel'
            self.old_filter.set(1)

            # In Confirmation mode plot detection points
            if self.mode.get() == 3:
                # Prepare for plotting detections
                ffBinName, meteorNo = self.confirmationListboxEntry.split()
                detectionCoordinates = get_FTPdetect_coordinates(self.ConfirmationInstance.FTPdetect_file_content, ffBinName, int(meteorNo))[0]

                img_array = markDetections(img_array, detectionCoordinates)

        elif self.filter.get() == 2: #colorized
            
            if (update_levels == True) or (self.hold_levels.get() == True): #Adjust levels
                minv_temp = self.min_lvl_scale.get()
                gamma_temp = self.gamma.get()
                maxv_temp = self.max_lvl_scale.get()
            else:
                maxv_temp = None
                gamma_temp = None
                minv_temp = None

            #Disable check buttons, as these parameters are not used
            self.dark_chk.config(state = DISABLED)
            self.flat_chk.config(state = DISABLED)
            self.deinterlace_chk.config(state = DISABLED)

            img_array = colorize_maxframe(readFF(img_path), minv_temp, gamma_temp, maxv_temp)
            
            self.img_name_type = 'colorized'
            self.old_filter.set(2)


        elif self.filter.get() == 3: # Detection only

            if self.mode.get() == 1: #Captured mode
                self.dark_chk.config(state = DISABLED)
                self.deinterlace_chk.config(state = DISABLED)
                img_array = max_nomean(readFF(img_path), flat_frame, flat_frame_scalar)
                self.img_name_type = 'max_nomean'

            elif self.mode.get() == 2: #Deteced mode
                self.dark_chk.config(state = NORMAL)
                self.deinterlace_chk.config(state = NORMAL)
                
                img_array = get_detection_only(readFF(img_path), start_frame, end_frame, flat_frame, flat_frame_scalar, dark_frame, self.deinterlace.get())
                self.img_name_type = 'detected_only'

            elif self.mode.get() == 3: # Confirmation
                self.dark_chk.config(state = NORMAL)
                self.deinterlace_chk.config(state = NORMAL)

                # Get detections only image
                img_array = get_detection_only(readFF(img_path), start_frame, end_frame, flat_frame, flat_frame_scalar, dark_frame, self.deinterlace.get())
                self.img_name_type = 'detected_only'

            self.old_filter.set(3)
                    

        elif self.filter.get() == 4: #Average pixel
            img_array = process_array(readFF(img_path).avepixel, flat_frame, flat_frame_scalar, dark_frame, self.deinterlace.get())
            
            self.img_name_type = 'avepixel'
            self.old_filter.set(4)

        elif self.filter.get() == 5: #Show only odd frame
            self.deinterlace_chk.config(state = DISABLED)
            img_array = process_array(readFF(img_path).maxpixel, flat_frame, flat_frame_scalar, dark_frame, deinterlace = False, field = 1)
            
            self.img_name_type = 'odd'
            self.old_filter.set(5)

        elif self.filter.get() == 6: #Show only even frame
            self.deinterlace_chk.config(state = DISABLED)
            img_array = process_array(readFF(img_path).maxpixel, flat_frame, flat_frame_scalar, dark_frame, deinterlace = False, field = 2)
            
            self.img_name_type = 'even'
            self.old_filter.set(6)

        elif self.filter.get() == 7: #Show individual frames

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
            
            self.img_name_type = 'frame_'+str(self.frame_slider_value)
            self.old_filter.set(7)
        
        elif self.filter.get() == 10: #Show video

            self.dark_chk.config(state = DISABLED)
            self.flat_chk.config(state = DISABLED)
            self.deinterlace_chk.config(state = DISABLED)
            self.hold_levels_chk.config(state = DISABLED)
            self.max_lvl_scale.config(state = DISABLED)
            self.min_lvl_scale.config(state = DISABLED)
            self.gamma_scale.config(state = DISABLED)

            self.video_thread = Video(app, img_path) #Create video object, pass binViewer class (app) to video object

            self.temp_frame.set(self.start_frame.get()) #Set temporary frame to start frame
            self.stop_video.set(False) #Set "stop video" flag to False -> video will run
            self.video_thread.start() #Start video thread
            self.starting_image = self.current_image #Set image to

            self.old_filter.set(10)

            return 0


        #Adjust levels
        if (update_levels == True) or (self.hold_levels.get() == True):
            if self.filter.get() != 2:
                img_array = adjust_levels(img_array, self.min_lvl_scale.get(), self.gamma.get(), self.max_lvl_scale.get())
        elif self.hold_levels.get() == True:
            pass #Don't reset values if hold levels button is on
        else:
            self.min_lvl_scale.set(0)
            self.max_lvl_scale.set(255)
            self.gamma_scale.set(0)
            self.gamma.set(1)


        self.img_data = img_array #For reference, otherwise it doesn't work

        temp_image = ImageTk.PhotoImage(img.fromarray(img_array).convert("RGB")) #Prepare for showing

        self.imagelabel.configure(image = temp_image)
        self.imagelabel.image = temp_image

        #Generate timestamp
        if self.filter.get() != 7:
            self.set_timestamp()

        self.old_image = self.current_image

    def set_timestamp(self, fps = None):
        """ Sets timestamp with given parameters """

        if fps == None:
            fps = " FFF"
        else:
            fps = str(fps).zfill(4)

        if self.correct_datafile_name(self.current_image):
            if self.data_type.get() == 1: #CAMS data type
                x = self.current_image.split('_')
                timestamp = x[1][0:4]+"-"+x[1][4:6]+"-"+x[1][6:8]+" "+x[2][0:2]+":"+x[2][2:4]+":"+x[2][4:6]+"."+x[3]+" "+fps
            else: #Skypatrol data type
                img_path = self.dir_path+os.sep+self.current_image
                (mode, ino, dev, nlink, uid, gid, size, atime, mtime, ctime) = os.stat(img_path)
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S.000", time.gmtime(mtime))+" "+fps


        else:
            timestamp = "YYYY-MM-DD HH:MM.SS.mms  FFF"

        self.timestamp_label.config(text = timestamp) #Change the timestamp label

    def wxDirchoose(self, initialdir, title, _selectedDir = '.'):
        """ Opens a dialog for choosing a directory. """
        _userCancel = ''
        app = wx.App()
        dialog = wx.DirDialog(None, title, style=1 ,defaultPath=initialdir, pos = (10,10))
        if dialog.ShowModal() == wx.ID_OK:
            _selectedDir = dialog.GetPath()
            return _selectedDir
        else:
            dialog.Destroy()
        return _userCancel


    def askdirectory(self):
        """Returns a selected directoryname."""

        # If changing during confirmation
        if self.mode.get() == 3:
            if self.confirmationEnd() == 0:
                return 0

        self.filter.set(1)
        self.stop_video.set(True) #Stop video every image update
        self.stop_confirmation_video.set(True)
        try:
            self.video_thread.join() #Wait for the video thread to finish
            del self.video_thread #Delete video thread
        except:
            pass

        # Terminate confirmation video thread if
        try:
            self.confirmation_video_thread.join()
            del self.confirmation_video_thread
        except:
            pass

        self.status_bar.config(text = "Opening directory...")

        old_dir_path = self.dir_path
        
        #Opens the file dialog
        self.dir_path = self.wxDirchoose(initialdir = self.dir_path, title = "Open the directory with FF*.bin files, then click OK")

        if self.dir_path == '':
            if os.path.exists(old_dir_path):
                self.dir_path = old_dir_path
            else:
                self.dir_path = os.getcwd()

        self.update_listbox(self.get_bin_list()) #Update listbox

        self.update_data_type()
       
        self.parent.wm_title("CMN_binViewer: "+self.dir_path) #Update dir label
        self.mode.set(1)
        self.filter.set(1)
        self.change_mode()

        self.move_top(0) #Move listbox cursor to the top

        self.write_config()

    def get_bin_list(self):
        """ Get a list of FF*.bin files in a given directory"""
        #bin_list = ["a", "b", "c", "d", "e", "f", "g"]
        bin_list = [line for line in os.listdir(self.dir_path) if self.correct_datafile_name(line)]
        return bin_list

    def update_listbox(self, bin_list):
        """ Updates the listbox with the current entries"""
        self.ff_list.delete(0, END)
        for line in sorted(bin_list):
            self.ff_list.insert(END, line)

    def save_image(self, extension, save_as):
        """ Saves the current image with given extension and parameters"""

        current_image = self.ff_list.get(ACTIVE)
        if current_image == '':
            tkMessageBox.showerror("Image error", "No image selected! Saving aborted.")
            return 0

        img_name = current_image+"_"+self.img_name_type+'.'+extension
        img_path = self.dir_path+os.sep+img_name
        if save_as == True:
            img_path = tkFileDialog.asksaveasfilename(initialdir = self.dir_path, parent = self.parent, title = "Save as...", initialfile = img_name, defaultextension = "."+extension)
            if img_path == '':
                return 0

        saveImage(self.img_data, img_path, self.print_name_status.get())

        self.status_bar.config(text = "Image saved: "+img_name)

    def copy_bin_to_sorted(self, event):
        """ Copies the current image FF*.bin file to the given directory"""
        if self.current_image == '':
            return 0

        if (os.sep in self.sort_folder_path.get()) or ('/' in self.sort_folder_path.get()):
            sorted_dir = self.sort_folder_path.get()
        else:
            sorted_dir = self.dir_path+os.sep+self.sort_folder_path.get()

        try:
            mkdir_p(sorted_dir)
        except:
            tkMessageBox.showerror("Path error", "The path does not exist or it is a root directory (e.g. C:\\): "+sorted_dir)
            return 0

        try:
            copy2(self.dir_path+os.sep+self.current_image, sorted_dir+os.sep+self.current_image) #Copy the file
        except:
            tkMessageBox.showerror("Copy error", "Could not copy file: "+self.current_image)
            return 0

        self.status_bar.config(text = "Copied: "+self.current_image) #Change the status bar

    def open_current_folder(self, event):
        """Opens current directory in windows explorer"""

        sorted_directory = self.dir_path+os.sep+self.sort_folder_path.get()
        try:
            os.startfile(sorted_directory)
        except:
            try:
                os.startfile(self.dir_path)
            except:
                tkMessageBox.showerror("Path not found", "Sorted folder is not created!")
                return 1
        return 0

    def make_master_dark(self):
        """ Makes the master dark frame"""
        self.status_bar.config(text = "Making master dark frame, please wait...")
        
        dark_dir = self.wxDirchoose(initialdir = self.dir_path, title = "Open the directory with dark frames, then click OK")

        if dark_dir == '': 
            self.status_bar.config(text = "Master dark frame making aborted!")
            return 0
        dark_file = tkFileDialog.asksaveasfilename(initialdir = dark_dir, parent = self.parent, title = "Choose the master dark file name", initialfile = "dark.bmp", defaultextension = ".bmp", filetypes = [('BMP files', '.bmp')])
        if dark_file == '': 
            self.status_bar.config(text = "Master dark frame making aborted!")
            return 0
        dark_dir = dark_dir.replace("/", os.sep)
        dark_file = dark_file.replace("/", os.sep)

        if (dark_file != '') and (dark_dir!=''):
            if make_flat_frame(dark_dir, dark_file, col_corrected = False, dark_frame = False) == False:
                tkMessageBox.showerror("Master dark frame", "The folder is empty!")
                self.status_bar.config(text = "Master dark frame failed!")
                return 0
        else:
            self.status_bar.config(text = "Files for master dark not chosen!")

        self.status_bar.config(text = "Master dark frame done!")
        tkMessageBox.showinfo("Master dark frame", "Master dark frame done!")

    def make_master_flat(self):
        """ Make master flat frame. A Directory which contains flat frames is chosen, file where flat frame will be saved, and an optional dark frame"""

        self.status_bar.config(text = "Making master flat frame, please wait...")
        
        flat_dir = self.wxDirchoose(initialdir = self.dir_path, title = "Open the directory with flat frames, then click OK")
        if flat_dir == '': 
            self.status_bar.config(text = "Master flat frame making aborted!")
            return 0
        flat_file = tkFileDialog.asksaveasfilename(initialdir = flat_dir, parent = self.parent, title = "Choose the master flat file name", initialfile = "flat.bmp", defaultextension = ".bmp", filetypes = [('BMP files', '.bmp')])
        if flat_file == '': 
            self.status_bar.config(text = "Master flat frame making aborted!")
            return 0

        flat_dir = flat_dir.replace("/", os.sep)
        flat_file = flat_file.replace("/", os.sep)

        dark_file = tkFileDialog.askopenfilename(initialdir = flat_dir, parent = self.parent, title = "OPTIONAL: Choose dark frame, if any. Click cancel for no dark frame.", initialfile = "dark.bmp", defaultextension = ".bmp", filetypes = [('BMP files', '.bmp')])

        
        if dark_file != '':
            dark_frame = load_dark(dark_file)
        else:
            dark_frame = False
        if make_flat_frame(flat_dir, flat_file, col_corrected = False, dark_frame = dark_frame) == False:
            tkMessageBox.showerror("Master flat frame", "The folder is empty!")
            self.status_bar.config(text = "Master flat frame failed!")
            return 0
        

        self.status_bar.config(text = "Master flat frame done!")
        tkMessageBox.showinfo("Master flat frame", "Master flat frame done!")

    def fireball_deinterlacing_process(self):
        """ Process individual frames (from start frame to end frame) by applying calibartion and deinterlacing them field by field. Used for manual fireball processing. """

        current_image = self.current_image
        if current_image == '':
            tkMessageBox.showerror("Image error", "No image selected! Saving aborted.")
            return 0

        dark_frame = None
        flat_frame = None
        flat_frame_scalar = None

        if self.dark_status.get() == True:
            dark_path = self.dir_path+os.sep+self.dark_name.get()
            try:
                dark_frame = load_dark(dark_path)
            except:
                pass

        if self.flat_status.get() == True:
            flat_path = self.dir_path+os.sep+self.flat_name.get()
            try:
                flat_frame, flat_frame_scalar = load_flat(flat_path)
            except:
                pass

        self.status_bar.config(text ="Processing individual frames and fields...")

        save_path = self.wxDirchoose(initialdir = self.dir_path, title = "Open the directory where you want to save individual frames by field, then click OK")

        #Abort the process if no path is chosen
        if save_path == '':
            return 0

        get_processed_frames(self.dir_path+os.sep+current_image, save_path+os.sep, self.data_type.get(), flat_frame, flat_frame_scalar, dark_frame, self.start_frame.get(), self.end_frame.get())

        self.status_bar.config(text ="Processing done!")


    def make_gif(self):
        """ Makes a GIF animation file with given options"""

        current_image = self.current_image
        if current_image == '':
            tkMessageBox.showerror("Image error", "No image selected! Saving aborted.")
            return 0

        dark_frame = None
        flat_frame = None
        flat_frame_scalar = None

        if self.dark_status.get() == True:
            dark_path = self.dir_path+os.sep+self.dark_name.get()
            try:
                dark_frame = load_dark(dark_path)
            except:
                pass

        if self.flat_status.get() == True:
            flat_path = self.dir_path+os.sep+self.flat_name.get()
            try:
                flat_frame, flat_frame_scalar = load_flat(flat_path)
            except:
                pass

        self.status_bar.config(text ="Making GIF, please wait... It can take up to 15 or more seconds, depending on the size and options")

        gif_name = current_image.split('.')[0]+"fr_"+str(self.start_frame.get())+"-"+str(self.end_frame.get())+".gif"

        gif_path = tkFileDialog.asksaveasfilename(initialdir = self.dir_path, parent = self.parent, title = "Save GIF animation", initialfile = gif_name, defaultextension = ".gif").replace("/", os.sep)
        #gif_path = (os.sep).join(gif_path.split(os.sep)[:-2])

        if gif_path == '': #Abort GIF making if no file is chosen
            return 0

        repeat_temp = self.repeat.get() #Get the repeat variable (the animation will loop if True)
        if (repeat_temp == 0) or (repeat_temp == False):
            repeat_temp = False
        else:
            repeat_temp = True

        #Adjust levels
        minv_temp = self.min_lvl_scale.get()
        gamma_temp = self.gamma.get()
        maxv_temp = self.max_lvl_scale.get()

        makeGIF(FF_input = current_image, start_frame = self.start_frame.get(), end_frame = self.end_frame.get(), ff_dir=self.dir_path, deinterlace = self.deinterlace.get(), print_name = self.gif_embed.get(), Flat_frame = flat_frame, Flat_frame_scalar = flat_frame_scalar, dark_frame = dark_frame, gif_name_parse = gif_path, repeat = repeat_temp, fps = self.fps.get(), minv = minv_temp, gamma = gamma_temp, maxv = maxv_temp, perfield = self.perfield_var.get())

        self.status_bar.config(text ="GIF done!")

        tkMessageBox.showinfo("GIF progress", "GIF saved!")

        self.write_config() #Write FPS to config file


    def get_detected_list(self, minimum_frames = 0):
        """ Gets a list of FF_bin files from the FTPdetectinfo with a list of frames. Used for composing the image while in DETECT mode
        minimum_frames: the smallest number of detections for showing the meteor"""
        minimum_frames = int(self.minimum_frames.get())
        
        def get_frames(frame_list):
            """Gets frames for given FF*.bin file in FTPdetectinfo"""
            if len(frame_list)<minimum_frames*2: #Times 2 because len(frames) actually contains every half-frame also
                ff_bin_list.pop()
                return None
            min_frame = int(float(frame_list[0]))
            max_frame = int(float(frame_list[-1]))
            ff_bin_list[-1].append((min_frame, max_frame))

        def convert2str(ff_bin_list):
            """ Converts list format: [['FF*.bin', (start_frame, end_frame)], ... ] to string format ['FF*.bin Fr start_frame - end_frame'] """
            str_ff_bin_list = []
            for line in ff_bin_list:
                str_ff_bin_list.append(line[0]+" Fr "+str(line[1][0]).zfill(3)+" - "+str(line[1][1]).zfill(3))

            return str_ff_bin_list


        ftpdetect_file = [line for line in os.listdir(self.dir_path) if ("FTPdetectinfo_" in line) and (".txt" in line) and (not "original" in line)]
        if len(ftpdetect_file) == 0:
            tkMessageBox.showerror("FTPdetectinfo error", "FTPdetectinfo file not found!")
            return False
        ftpdetect_file = ftpdetect_file[0]
        try:
            FTPdetect_file_content = open(self.dir_path+os.sep+ftpdetect_file).readlines()
        except:
            tkMessageBox.showerror("File error", "Could not open file: "+ftpdetect_file)
            return False

        if int(FTPdetect_file_content[0].split('=')[1]) == 0: #Solving issue when no meteors are in the file
            return []

        ff_bin_list = []

        skip = 0
        frame_list = []
        for line in FTPdetect_file_content[12:]:
            #print line

            if ("-------------------------------------------------------" in line):
                get_frames(frame_list)
                

            if skip>0:
                skip -= 1
                continue

            line = line.replace('\n', '')

            if ("FF in line") and (".bin" in line):
                ff_bin_list.append([line.strip()])
                skip = 2
                del frame_list
                frame_list = []
                continue
            
            frame_list.append(line.split()[0])

        get_frames(frame_list) #Writing the last FF bin file frames in a list

        return ff_bin_list, convert2str(ff_bin_list) #Converts list to a list of strings

    def get_logsort_list(self, logsort_name = "LOG_SORT.INF", minimum_frames = 0):
        """ Gets a list of BMP files from the LOG_SORT.INF with a list of frames. Used for composing the image while in DETECT mode
            minimum_frames: the smallest number of detections for showing the meteor"""

        minimum_frames = int(self.minimum_frames.get())

        def get_frames(frame_list):
            """Gets frames for given BMP file in LOGSORT"""
            if len(frame_list)<minimum_frames*2: #Times 2 because len(frames) actually contains every half-frame also
                image_list.pop()
                return None
            min_frame = int(float(frame_list[0]))
            max_frame = int(float(frame_list[-1]))
            image_list[-1].append((min_frame, max_frame))

        def convert2str(ff_bin_list):
            """ Converts list format: [['FF*.bin', (start_frame, end_frame)], ... ] to string format ['FF*.bin Fr start_frame - end_frame'] """
            str_ff_bin_list = []
            for line in ff_bin_list:
                str_ff_bin_list.append(line[0]+" Fr "+str(line[1][0]).zfill(4)+" - "+str(line[1][1]).zfill(4))

            return str_ff_bin_list

        logsort_path = self.dir_path+os.sep+logsort_name
        
        if not os.path.isfile(logsort_path):
            tkMessageBox.showerror("LOG_SORT.INF error", "LOG_SORT.INF file not found!")

        try:
            logsort_contents = open(logsort_path).readlines()
        except:
            tkMessageBox.showerror("File error", "Could not open file: "+logsort_path)
            return False

        if logsort_contents[5] == '999': #Return empty list if logsort is empty
            return []

        image_list = []
        frame_list = []
        met_no = 0
        first = True
        for line in logsort_contents[5:]:

            if line == '999':
                break

            line = line.split()

            img_name = line[4].split('_')[1]+'.bmp'
            met_no = int(line[0])

            if not img_name in [image[0] for image in image_list] or old_met != met_no:
                if first != True:
                    get_frames(frame_list)
                else:
                    first = False

                image_list.append([img_name])

                old_met = met_no
                del frame_list
                frame_list = []
                continue
                
            frame_list.append(line[1])

        get_frames(frame_list)

        return image_list, convert2str(image_list)

    def update_scales(self, value):
        """ Updates the size of levels scales, to make the appearence that there are 2 sliders on one scale """
        size_var = 0.8
        min_value = self.min_lvl_scale.get()
        max_value = self.max_lvl_scale.get()
        middle = (min_value+max_value)/2

        min_size = middle * size_var
        max_size = (255 - middle) * size_var

        self.min_lvl_scale.config(from_ = 0, to = middle - 1, length = min_size)
        self.max_lvl_scale.config(from_ = middle +1, to = 255, length = max_size)

        self.gamma.set(1/10**(self.gamma_scale.get()))
        self.gamma_scale.config(label = "Gamma:             "+"{0:.2f}".format(round(self.gamma.get(), 2)))

        self.update_image(0, update_levels = True)
        

    def change_mode(self):
        """ Changes the current mode"""
        if self.mode.get()==1: #Captured mode

            #Enable all filters
            self.maxpixel_btn.config(state = NORMAL)
            self.colored_btn.config(state = NORMAL)
            self.avgpixel_btn.config(state = NORMAL)
            self.odd_btn.config(state = NORMAL)
            self.even_btn.config(state = NORMAL)

            self.min_frames_entry.config(state = DISABLED) #Disable the entry of minimum frame number

            self.filter.set(1) #Set filter to maxframe

            old_image = self.current_image #Preserve the image position
            
            temp_bin_list = self.get_bin_list()
            self.update_listbox(temp_bin_list) #Update listbox
            
            if old_image in temp_bin_list:
                temp_index = temp_bin_list.index(old_image)
                self.move_index(temp_index) #Move to old image position
            else:
                self.move_top(0) #Move listbox cursor to the top

            self.start_frame.set(0)
            if self.data_type.get() == 1: #CAMS data type
                self.end_frame.set(255)
                self.frame_scale.config(to = 255)
            else: #Skypatrol data type
                self.end_frame.set(1500)
                self.frame_scale.config(to = 1500)

        elif self.mode.get() == 2: #Detected mode
            
            if self.data_type.get() == 1: #CAMS data type
                detected_list = self.get_detected_list() #Get a list of FF*.bin files from FTPdetectinfo
            else: #Skypatrol data type
                detected_list = self.get_logsort_list()

            if detected_list == False:
                self.mode.set(1)
                return 0
            elif detected_list[0] == []:
                tkMessageBox.showinfo("FTPdetectinfo info", "No detections in the FTPdetectinfo file!")
                self.mode.set(1)
                return 0


            self.min_frames_entry.config(state = NORMAL) #Enable the entry of minimum frame number

            ff_bin_list, str_ff_bin_list = detected_list

            self.detection_dict = dict(zip(str_ff_bin_list, ff_bin_list))

            if not self.filter.get() == 10: #Dont change if video filter was set
                self.filter.set(3) #Set filter to Detection only

            # Disable all other filters
            self.maxpixel_btn.config(state = DISABLED)
            self.colored_btn.config(state = DISABLED)
            self.avgpixel_btn.config(state = DISABLED)
            self.odd_btn.config(state = DISABLED)
            self.even_btn.config(state = DISABLED)

            old_image = self.current_image #Get old image name

            self.update_listbox(str_ff_bin_list)
            try:
                temp_index = str_ff_bin_list.index([bin for bin in str_ff_bin_list if old_image in bin][0])
                self.move_index(temp_index) #Move to old image position
            except:
                self.move_top(0) #Move listbox cursor to the top

        elif self.mode.get() == 3: # Confirmation mode
            #Enable all filters
            self.maxpixel_btn.config(state = NORMAL)
            self.colored_btn.config(state = NORMAL)
            self.avgpixel_btn.config(state = NORMAL)
            self.odd_btn.config(state = NORMAL)
            self.even_btn.config(state = NORMAL)

            self.min_frames_entry.config(state = DISABLED) #Disable the entry of minimum frame number

            self.filter.set(3) #Set filter to detection only

            self.confirmationDict = self.ConfirmationInstance.getMeteorList()

            listbox_entries = []
            for key in self.confirmationDict:
                listbox_entries.append(key+' '+self.confirmationDict[key][0])

            self.update_listbox(listbox_entries)
            self.move_top(0)

    def confirmationStart(self):

        # Variable for checking previous index
        self.old_index = 0

        # Check if viewing Skypatrol images
        if self.data_type.get() == 2:
            tkMessageBox.showerror("Skypatrol", "Confirmation is only available for CAMS standard files!")
            return 0

        confirmationDirectoryName = "ConfirmedFiles"
        
        upDir = self.dir_path.split(os.sep)[-2]
        if upDir == "CapturedFiles":
            if not tkMessageBox.askyesno("Directory name", "Are you sure you want to do confirmation on CapturedFiles?"):
                return 0
        elif upDir != "ArchivedFiles":
            tkMessageBox.showerror("Directory error", "You can only do confirmation in ArchivedFiles or CapturedFiles directory!")
            return 0

        nightDir = self.dir_path.split(os.sep)[-1]

        confirmationDirectory = (os.sep).join(self.dir_path.split(os.sep)[:-2]+[confirmationDirectoryName, nightDir])

        mkdir_p(confirmationDirectory)

        image_list = []
        ftpDetectFile = ''
        for image in os.listdir(self.dir_path):
            if self.correct_datafile_name(image):
                image_list.append(image)
                continue
            if ('FTPdetectinfo' in image) and ('.txt' in image):
                ftpDetectFile = image

        if ftpDetectFile == '':
            tkMessageBox.showerror("FTPdetectinfo error", "No FTPdetectinfo file could be found in directory: "+self.dir_path)
            self.confirmationFinish()
            return 0

        self.ConfirmationInstance = Confirmation(image_list, self.dir_path+os.sep+ftpDetectFile, confirmationDirectory, minimum_frames = 0)

        if tkMessageBox.askyesno("Confirmation", "Confirmation key bindings:\n  Enter - confirm\n  Down arrow - reject\n\nThere are "+str(len(self.ConfirmationInstance.getImageList(0)))+" images to be confirmed, do you want to proceed?"):

            # Disable mode buttons during confirmation
            self.captured_btn.config(state = DISABLED)
            self.detected_btn.config(state = DISABLED)

            self.mode.set(3)
            self.change_mode()

            # Change key binding
            self.parent.bind("<Return>", self.confirmationYes) # Enter
            self.parent.bind("<Down>", self.confirmationNo) # Down arroy
            self.parent.unbind("<Prior>") #Page up
            self.parent.unbind("<Next>") #Page up

            self.confirmationMenu.entryconfig("Start", state = "disabled")
            self.confirmationMenu.entryconfig("End", state = "normal")

            # Set gamma a bit higher and turn of deinterlace
            self.hold_levels.set(True)
            self.gamma_scale.set(-0.12) # Set gamma to about 1.3, so the meteors are visible better
            self.deinterlace.set(True)

            self.update_layout()
        else:
            self.confirmationFinish()

            

    def confirmationYes(self, event):

        # Confirm current image in Confirmation instance

        self.ConfirmationInstance.confirmImage(self.confirmationListboxEntry)

        newEntry = self.confirmationListboxEntry+" Y  "

        if not self.ff_list is self.parent.focus_get():
            self.ff_list.focus()

        cur_index = int(self.ff_list.curselection()[0])

        self.ff_list.insert(ACTIVE, newEntry)
        self.ff_list.delete(ACTIVE)

        # Change text color to green
        self.ff_list.itemconfig(cur_index, fg = 'green')

        next_index = cur_index + 1
        size = self.ff_list.size()-1
        if next_index > size:
            next_index = size
        
        self.ff_list.activate(next_index)
        self.ff_list.selection_clear(0, END)
        self.ff_list.selection_set(next_index)
        self.ff_list.see(next_index)

        self.update_image(0)

        # Detect list end
        if cur_index == self.ff_list.size()-1:
            self.confirmationEnd()


    def confirmationNo(self, event):

        # Reject current image in Confirmation instance

        if not self.ff_list is self.parent.focus_get():
            self.move_img_down(0)

        cur_index = int(self.ff_list.curselection()[0])

        size = self.ff_list.size()-1

        # If it isn't the last element
        if (cur_index != size) or (cur_index != self.old_index):

            prev_index = cur_index - 1
            if prev_index < 0:
                prev_index = 0
            
            self.ff_list.activate(prev_index)
            self.ff_list.selection_clear(0, END)
            self.ff_list.selection_set(prev_index)
            self.ff_list.see(prev_index)

        self.update_current_image()

        self.ConfirmationInstance.rejectImage(self.confirmationListboxEntry)

        newEntry = self.confirmationListboxEntry+"   N"

        
        # If the last element is selected
        if (cur_index == size) and (cur_index == self.old_index):
            prev_index = cur_index

            self.ff_list.delete(END)
            self.ff_list.insert(END, newEntry)

            self.reject_finish_flag = True

        else:
            self.reject_finish_flag = False
            self.ff_list.insert(prev_index, newEntry)
            self.ff_list.delete(cur_index)

        # Change text color to green
        self.ff_list.itemconfig(prev_index, fg = 'red')

        # Activate next
        self.ff_list.activate(cur_index)
        self.ff_list.selection_clear(0, END)
        self.ff_list.selection_set(cur_index)
        self.ff_list.see(cur_index)

        self.update_current_image()

        self.old_index = cur_index

        # Detect list end
        if (cur_index == size) and (cur_index == self.old_index) and (self.reject_finish_flag):
            self.confirmationEnd()



    def confirmationEnd(self):

        unchecked_count = len(self.ConfirmationInstance.getImageList(0))

        if unchecked_count > 0:
            if tkMessageBox.askyesno("Confirmation", "Are you sure you want to exit confirmation? You still have "+str(unchecked_count)+" unchecked images."):
                if not tkMessageBox.askyesno("Confirmation", "Do you want to save confirmed images to ConfirmationFiles?"):
                    self.confirmationFinish()
                    return 2
            else:
                return 0

        confirmed_files = self.ConfirmationInstance.getImageList(1)
        confirmed_count = len(confirmed_files)
        rejected_count = len(self.ConfirmationInstance.getImageList(-1))

        FTPdetectinfoExport = self.ConfirmationInstance.exportFTPdetectinfo()

        # Copy confirmed images and write modified FTPdetectinfo, if any files were confirmed

        if len(confirmed_files):
            for ff_bin in confirmed_files:

                dir_contents = os.listdir(self.dir_path)

                if ff_bin in dir_contents:
                    copy2(self.dir_path+os.sep+ff_bin, self.ConfirmationInstance.confirmationDirectory+os.sep+ff_bin)

            ftpDetectFile = ''
            for dir_file in dir_contents:
                if 'FTPdetectinfo' in dir_file:
                    copy2(self.dir_path+os.sep+dir_file, self.ConfirmationInstance.confirmationDirectory+os.sep+"".join(dir_file.split('.')[:-1])+'_ORIGINAL.txt')
                    ftpDetectFile = dir_file
                    continue
                elif ('.txt' in dir_file) or ('.inf' in dir_file) or ('.rpt' in dir_file) or ('.log' in dir_file) or ('.hmm' in dir_file) or ('.cal' in dir_file):
                    copy2(os.dir_path+os.sep+dir_file, self.ConfirmationInstance.confirmationDirectory+os.sep+dir_file)

            if ftpDetectFile == '':
                tkMessageBox.showerror("FTPdetectinfo", "No FTPdetectinfo file found in: "+self.dir_path)
                return 1

            newFTPdetectinfo = open(self.ConfirmationInstance.confirmationDirectory+os.sep+ftpDetectFile, 'w')
            for line in FTPdetectinfoExport:
                newFTPdetectinfo.write(line)

            newFTPdetectinfo.close()


        tkMessageBox.showinfo("Confirmation", "Confirmation statistics:\n  Confirmed: "+str(confirmed_count)+"\n  Rejected: "+str(rejected_count)+"\n  Unchecked: "+str(unchecked_count))

        self.confirmationFinish()

        return 2
        

    def confirmationFinish(self):
        """ Finish confirmation procedure by reseting GUI settings to normal. """

        del self.ConfirmationInstance
        # Change key bindings to previous
        self.parent.bind("<Return>", self.copy_bin_to_sorted) # Enter
        self.parent.bind("<Down>", self.move_img_down) # Down arrow
        self.parent.bind("<Prior>", self.captured_mode_set) #Page up
        self.parent.bind("<Next>", self.detected_mode_set) #Page up

        # Re-enable mode buttons
        self.captured_btn.config(state = NORMAL)
        self.detected_btn.config(state = NORMAL)

        # Re-enable menu
        self.confirmationMenu.entryconfig("Start", state = "normal")
        self.confirmationMenu.entryconfig("End", state = "disabled")

        self.mode.set(1)
        self.change_mode()

        self.update_layout()

        self.update_image(0)



    def show_about(self):
        tkMessageBox.showinfo("About", 
            """CMN_binViewer version: """+str(version)+"""\n
            Croatian Meteor Network\n
            http://cmn.rgn.hr/\n
            Copyright © 2015 Denis Vida
            E-mail: denis.vida@gmail.com\n
Reading FF*.bin files: based on Matlab scripts by Peter S. Gural
images2gif: Copyright © 2012, Almar Klein, Ant1, Marius van Voorden
gifsicle: Copyright © 1997-2013 Eddie Kohler""")

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
                - Insert - toggle Hold levels""")


    def onExit(self):
        self.quit()


    def initUI(self):
        """ Initialize GUI elements"""
      
        self.parent.title("CMN_binViewer")
        
        #Configure the style of each element
        s = Style()
        s.configure("TButton", padding=(0, 5, 0, 5), font='serif 10', background = global_bg)
        s.configure('TLabelframe.Label', foreground =global_fg, background=global_bg)
        s.configure('TLabelframe', foreground =global_fg, background=global_bg, padding=(3, 3, 3, 3))
        s.configure("TRadiobutton", foreground = global_fg, background = global_bg)
        s.configure("TLabel", foreground = global_fg, background = global_bg)
        s.configure("TCheckbutton", foreground = global_fg, background = global_bg)
        s.configure("Vertical.TScrollbar", background=global_bg, troughcolor = global_bg)
        #s.configure('TScale', sliderthickness = 1)
        
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

        #Make menu
        self.menuBar = Menu(self.parent)
        self.parent.config(menu=self.menuBar)

        #File menu
        fileMenu = Menu(self.menuBar, tearoff=0)
        fileMenu.add_command(label = "Open FF*.bin folder", command = self.askdirectory)
        
        fileMenu.add_separator()
        
        fileMenu.add_command(label="Exit", underline=0, command=self.onExit)
        self.menuBar.add_cascade(label="File", underline=0, menu=fileMenu)  

        #Data type menu
        datatypeMenu = Menu(self.menuBar, tearoff = 0)
        datatypeMenu.add_checkbutton(label = "Auto", onvalue = 0, variable = self.data_type_var, command = self.update_data_type)
        datatypeMenu.add_separator()
        datatypeMenu.add_checkbutton(label = "CAMS", onvalue = 1, variable = self.data_type_var, command = self.update_data_type)
        datatypeMenu.add_checkbutton(label = "Skypatrol", onvalue = 2, variable = self.data_type_var, command = self.update_data_type)
        self.menuBar.add_cascade(label = "Data type", underline = 0, menu = datatypeMenu)

        # Confirmation menu
        self.confirmationMenu = Menu(self.menuBar, tearoff = 0)
        self.confirmationMenu.add_command(label = "Start", underline = 0, command = self.confirmationStart)
        self.confirmationMenu.add_command(label = "End", underline = 0, command = self.confirmationEnd)
        self.confirmationMenu.entryconfig("End", state = "disabled")
        self.menuBar.add_cascade(label = "Confirmation", underline = 0, menu = self.confirmationMenu)

        #Process Menu
        processMenu = Menu(self.menuBar, tearoff=0)      
        processMenu.add_command(label = "Make master dark frame", command = self.make_master_dark)
        processMenu.add_command(label = "Make master flat frame", command = self.make_master_flat)
        
        self.menuBar.add_cascade(label="Process", underline=0, menu=processMenu)

        #Layout menu
        layoutMenu = Menu(self.menuBar, tearoff = 0)
        layoutMenu.add_checkbutton(label = "Vertical layout", onvalue = True, offvalue = False, variable = self.layout_vertical, command = self.update_layout)
        layoutMenu.add_checkbutton(label = "Horizontal layout", onvalue = False, offvalue = True, variable = self.layout_vertical, command = self.update_layout)
        self.menuBar.add_cascade(label = "Layout", menu = layoutMenu)

        #Window menu
        self.windowMenu = Menu(self.menuBar, tearoff = 0)
        self.windowMenu.add_checkbutton(label = "Save image", onvalue = True, offvalue = False, variable = self.save_image_frame, command = self.update_layout)
        self.windowMenu.add_checkbutton(label = "Image levels", onvalue = True, offvalue = False, variable = self.image_levels_frame, command = self.update_layout)
        self.windowMenu.add_checkbutton(label = "Save animation", onvalue = True, offvalue = False, variable = self.save_animation_frame, command = self.update_layout)
        self.menuBar.add_cascade(label = "Window", menu = self.windowMenu)

        #Help Menu
        helpMenu = Menu(self.menuBar, tearoff=0)
        helpMenu.add_command(label = "Key bindings", command = self.show_key_bindings)
        helpMenu.add_command(label = "About", command = self.show_about)
        self.menuBar.add_cascade(label = "Help", underline=0, menu=helpMenu)


        #Panel for mode
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

        #Calibration & image features

        calib_panel = LabelFrame(self, text=' Calibration & image features ')
        calib_panel.grid(row = 3, column = 0, columnspan = 2, rowspan = 1, sticky = "NWE")

        self.dark_chk = Checkbutton(calib_panel, text = "Dark frame", variable = self.dark_status, command = lambda: self.update_image(0))
        self.dark_chk.grid(row = 4, column = 0, sticky = "W")

        dark_entry = StyledEntry(calib_panel, textvariable = self.dark_name, width = 25)
        dark_entry.grid(row = 4, column = 1, sticky = "W")

        dark_button = StyledButton(calib_panel, text = "Open", command = self.open_dark_path, width = 5)
        dark_button.grid(row =4, column = 2, sticky ="W")

        self.flat_chk = Checkbutton(calib_panel, text = "Flat frame", variable = self.flat_status, command = lambda: self.update_image(0))
        self.flat_chk.grid(row = 5, column = 0, sticky = "W")

        flat_entry = StyledEntry(calib_panel, textvariable = self.flat_name, width = 25)
        flat_entry.grid(row = 5, column = 1, sticky = "W")

        flat_button = StyledButton(calib_panel, text = "Open", command = self.open_flat_path, width = 5)
        flat_button.grid(row = 5, column = 2, sticky ="W")

        self.deinterlace_chk = Checkbutton(calib_panel, text = "Deinterlace", variable = self.deinterlace, command = lambda: self.update_image(0))
        self.deinterlace_chk.grid(row = 6, column = 0, sticky = "W")

        self.hold_levels_chk = Checkbutton(calib_panel, text = 'Hold levels', variable = self.hold_levels)
        self.hold_levels_chk.grid(row = 7, column = 0, sticky = "W")



        #Listbox
        self.scrollbar = Scrollbar(self)
        self.ff_list = Listbox(self, width = 47, yscrollcommand=self.scrollbar.set, exportselection=0, activestyle = "none", bg = global_bg, fg = global_fg)
        # Listbox position set in update_layout
        
        self.ff_list.bind('<<ListboxSelect>>', self.update_image) 
        self.scrollbar.config(command = self.ff_list.yview)

        #Filters panel
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

        #Frames
        self.frames_btn = Radiobutton(filter_panel, text = "Frames", variable = self.filter, value = 7, command = lambda: self.update_image(0))
        self.frames_btn.grid(row = 2, column = 9)

        #Video
        self.video_btn = Radiobutton(filter_panel, text = "VIDEO", variable = self.filter, value = 10, command = lambda: self.update_image(0))
        self.video_btn.grid(row = 2, column = 10)



        #Sort panel
        sort_panel = LabelFrame(self, text=' Sort FF*.bins ')
        sort_panel.grid(row = 1, column = 5, sticky = "W", padx=2, pady=5, ipadx=5, ipady=5)

        sort_folder_label = Label(sort_panel, text = "Folder:")
        sort_folder_label.grid(row = 2, column = 4, sticky = "W")
        sort_folder_entry = StyledEntry(sort_panel, textvariable = self.sort_folder_path, width = 15)
        sort_folder_entry.grid(row = 3, column = 4)

        #previous_button = StyledButton(sort_panel, text ="<", width=3, command = lambda: self.move_img_up(0))
        #previous_button.grid(row = 2, column = 6, rowspan = 2)

        copy_button = StyledButton(sort_panel, text ="Copy", width=5, command = lambda: self.copy_bin_to_sorted(0))
        copy_button.grid(row = 2, column = 7, rowspan = 2)
        open_button = StyledButton(sort_panel, text ="Show folder", command = lambda: self.open_current_folder(0))
        open_button.grid(row = 2, column = 8, rowspan = 2)

        #next_button = StyledButton(sort_panel, text =">", width=3, command = lambda: self.move_img_down(0))
        #next_button.grid(row = 2, column = 9, rowspan = 2)

        #Image
        try: #Show the TV test card image on open
            noimage_data = open('noimage.bin', 'rb').read()
            noimage = PhotoImage(data = noimage_data)
        except:
            noimage = None

        self.imagelabel = Label(self, image = noimage)
        self.imagelabel.image = noimage
        self.imagelabel.grid(row=3, column=3, rowspan = 4, columnspan = 3)

        # Confirmation video
        blankImage = ImageTk.PhotoImage(img.fromarray(128+np.zeros(shape=(256, 256))).convert("RGB"))
        self.confirmationVideoLabel = Label(self, image = blankImage)
        self.confirmationVideoLabel.image = blankImage
        # Position set in update_layout

        #Timestamp label
        self.timestamp_label = Label(self, text = "YYYY-MM-DD HH:MM.SS.mms  FFF", font=("Courier", 12))
        self.timestamp_label.grid(row = 7, column = 5, sticky = "E")
        #self.timestamp_label.grid(row = 2, column = 3, sticky = "WNS")
        
        #Save buttons
        self.save_panel = LabelFrame(self, text=' Save image ') #Position set in update layout
        

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

        self.print_name_btn = Checkbutton(self.save_panel, text = "Embed name", variable = self.print_name_status) #Position set in update_label
        

        #Levels
        self.levels_label = LabelFrame(self, text =" Image levels ") #position set in update_layout
        

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

        self.hold_levels_chk_horizontal = Checkbutton(self.levels_label, text = 'Hold levels', variable = self.hold_levels) #Position set in update_layout
        

        #Animation
        self.animation_panel = LabelFrame(self, text=' Save animation ') #Position set in update_layout
        

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

        self.gif_make_btn = StyledButton(self.animation_panel, text ="GIF", command = self.make_gif, width = 10) #Position set in update_layout


        #Frame slider
        self.frames_slider_panel = LabelFrame(self, text=' Frame ') #Position set in update_layout
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



        
        #Status bar
        self.status_bar = Label(self, text="Start", relief="sunken", anchor="w")
        self.status_bar.grid(row = 11, column = 0, columnspan = 15, sticky = "WE")

        self.update_layout()
        

def log_timestamp():
    """ Returns timestamp for logging """
    return datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')  

class Catcher: 
    """ Used for catching unhandled exceptions """
    def __init__(self, func, subst, widget):
        self.func = func 
        self.subst = subst
        self.widget = widget
    def __call__(self, *args):
        try:
            if self.subst:
                args = apply(self.subst, args)
            return apply(self.func, args)
        except SystemExit, msg:
            raise SystemExit, msg
        except:
            log.critical(traceback.format_exc())
            tkMessageBox.showerror("Unhandled exception", "An unhandled exception has occured!\nPlease see the last logfile in the "+log_directory+" for more information!")
            sys.exit()

if __name__ == '__main__':

    # Catch unhandled exceptions in Tkinter
    tk.CallWrapper = Catcher

    # Initialize logging
    log_directory = os.path.abspath('.')+os.sep+log_directory+os.sep

    mkdir_p(log_directory)
    log = logging.getLogger(__name__)
    log.setLevel(logging.INFO)

    log_file=log_directory+log_timestamp()+'.log'
    handler = logging.handlers.TimedRotatingFileHandler(log_file, when='D', interval=1) #Log to a different file each day
    handler.setLevel(logging.INFO)

    formatter = logging.Formatter(fmt='%(asctime)s-%(levelname)s-%(module)s-line:%(lineno)d - %(message)s', datefmt='%Y/%m/%d %H:%M:%S')
    handler.setFormatter(formatter)
    log.addHandler(handler)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter(fmt='%(asctime)s-%(levelname)s: %(message)s', datefmt='%Y/%m/%d %H:%M:%S')
    ch.setFormatter(formatter)
    log.addHandler(ch)

    log.info("Program start")
    log.info("Version: "+str(version))


    root = Tk()
    try:
        root.iconbitmap(r'.'+os.sep+'icon.ico')
    except:
        pass
    app = BinViewer(root)
    
    root.mainloop()
    