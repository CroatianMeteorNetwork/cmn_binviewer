# -*- coding: utf-8 -*-
# Copyright notice (Revised BSD License)

# Copyright (c) 2015, Denis Vida
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

class Confirmation:
    """ Class for managing the CAMS confirmation procedure. 
    """
    def __init__(self, img_list, FTP_detect_file, confirmationDirectory, minimum_frames):
        """ Inputs:
            img_list: a list of *.bins e.g. [FF451_20140819_015438_468_0513536.bin, FF451_20140819_013439_953_0483584.bin, FF451_20140819_005544_078_0425216.bin] 
            FTP_detect_file: full path to the FTPdetectinfo file 
            """

        self.img_list = img_list
        self.FTP_detect_file = FTP_detect_file

        # Load FTPdetectinfo file
        self.FTPdetect_file_content = open(self.FTP_detect_file).readlines()
        self.FTPdetect_file_content = self.removeLastSeparator(self.FTPdetect_file_content)

        self.confirmationDirectory = confirmationDirectory

        # Check if all *.bin images in the folder correspond to the images in FTPdetectinfo file

        # Get a list of FF_bin files from FTPdetectinfo file
        FTP_bin_list = self.getFTPdetectFrames(minimum_frames)

        # Dictionary of images and their confirmation status (X - not checked, Y - confirmed, N - rejected), all images are initialized with "X"
        self.img_dict = {}

        for FF_bin_file in FTP_bin_list:

            if FF_bin_file[0] in self.img_list:
                entry = FF_bin_file[0]+' '+FF_bin_file[1][0]
                self.img_dict[entry] = [' X ', FF_bin_file[1][1], FF_bin_file[1][2]]

    def removeLastSeparator(self, FTPdetect_file_content):
        """ Removes last separator in the FTPdetectinfo file, as it may interfere with normal operation. """

        if len(FTPdetect_file_content) > 1:
            if '----------' in FTPdetect_file_content[-1]:
                FTPdetect_file_content.pop()

        return FTPdetect_file_content

    def getMeteorList(self):
        """ Returns the dictionary of meteors with their current status. 
        """
        return self.img_dict

    def getImageList(self, status = 1):
        """ Returns the dictionary of non-repeating images by thier status.

        1 - confirmed
        0 - unckecked
       -1 - rejected
        """
        if status == 1:
            status_string = 'Y'
        elif status == -1:
            status_string = 'N'
        else:
            status_string = 'X'

        image_list = []

        # Sort dictionary entries first!
        for key in sorted(list(self.img_dict.keys())):
            if status_string in self.img_dict[key][0]:
                image_list.append(key.split()[0])

        return image_list

    def confirmImage(self, img_name):
        """ Confirm image by setting "Y" to it. 
        """
        self.img_dict[img_name][0] = 'Y  '

    def rejectImage(self, img_name):
        """ Reject image by setting "N" to it. 
        """
        self.img_dict[img_name][0] = '  N'

    def exportFTPdetectinfo(self):
        """ Export confirmed meteors to new FTPdetectinfo file (return a list of file rows). 
        """

        met_count = self.FTPdetect_file_content[0]
        header = self.FTPdetect_file_content[1:11]

        header[3] = "FF  folder = " + self.confirmationDirectory+'\n'

        entries_dict = {}
        entries_list = []
        entry_temp = []


        for line in self.FTPdetect_file_content[12:]:

            if ("-------------------------------------------------------" in line):
                entries_list.append(entry_temp)
                del entry_temp
                entry_temp = []
                continue

            entry_temp.append(line)

        entries_list.append(entry_temp)

        for line in entries_list:
            key = line[0].replace('\n', '').strip()+' '+line[2].split()[1]
            entries_dict[key] = line
        
        export_list = ["-------------------------------------------------------\n"]
        export_list += header

        export_count = 0
        for key in sorted(list(self.img_dict.keys())):
            if 'Y' in self.img_dict[key][0]:
                export_list.append("-------------------------------------------------------\n")
                export_list += entries_dict[key]
                export_count += 1

        export_list[0] = 'Meteor Count = '+str(export_count).zfill(6)+'\n'

        return export_list


    def getFTPdetectFrames(self, minimum_frames):
        """ Returns a list of FF*.bin files with coresponding frames for a detected meteor in format [["FF*bin", (start_frame, end_frame)]]. 
        """

        def get_frames(frame_list, met_no, HT_rho, HT_phi):
            if len(frame_list)<minimum_frames*2:  # Times 2 because len(frames) actually contains every half-frame also
                ff_bin_list.pop()
                return None
            min_frame = int(float(frame_list[0]))
            max_frame = int(float(frame_list[-1]))
            ff_bin_list[-1].append((met_no, min_frame, max_frame, HT_rho, HT_phi))

            #print len(frame_list)

        if int(self.FTPdetect_file_content[0].split('=')[1]) == 0:  # Solving issue when no meteors are in the file
            return []

        ff_bin_list = []

        skip = 0
        met_no_flag = False
        met_no = "XXXX"
        frame_list = []
        for line in self.FTPdetect_file_content[12:]:
            #print line

            if ("-------------------------------------------------------" in line):
                get_frames(frame_list, met_no, HT_rho, HT_phi)
                

            if skip>0:
                skip -= 1
                continue

            line = line.replace('\n', '')

            # Read the line with FF_bin name
            if ("FF" in line) and (".bin" in line):
                ff_bin_list.append([line.strip()])
                skip = 1
                met_no_flag = True
                del frame_list
                frame_list = []
                continue

            # Read meteor info from the second event line
            if met_no_flag == True:
                line = line.split()
                met_no = line[1]
                HT_rho = line[8]
                HT_phi = line[9]
                met_no_flag = False
                continue
            
            frame_list.append(line.split()[0])

        # Check if there are no detections
        if len(frame_list) == 0:
            return []

        get_frames(frame_list, met_no, HT_rho, HT_phi)  # Writing the last FF bin file frames in a list

        return ff_bin_list

## TEST EXAMPLES OF USAGE
# temp_list = ["FF451_20140819_021619_203_0546048.bin", "FF451_20140819_020544_234_0530176.bin", "FF451_20140819_013114_640_0478464.bin"]

# # Initialize confirmation instance
# confInstance = Confirmation(temp_list, "FTPdetectinfo_0451_2014_08_18.txt", minimum_frames = 0)

# print confInstance.getMeteorList()
# confInstance.confirmImage("FF451_20140819_013114_640_0478464.bin 0001")
# confInstance.confirmImage("FF451_20140819_020544_234_0530176.bin 0001")
# confInstance.rejectImage("FF451_20140819_021619_203_0546048.bin 0001")
# print confInstance.getMeteorList()

# print 'Confirmed images: ', confInstance.getImageList(1)

# print confInstance.exportFTPdetectinfo('C:\\HMM_ADAPT_exe\\CAMS\\ConfirmedFiles\\2014_08_18_20_12_04\\')