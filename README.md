# CMN_binViewer
CMN_binViewer -- view, organize, calibrate and confirm CAMS standard meteor data

CMN_binViewer came into existence during the second part of August 2014, as a result of a dire need of new viewing software for [CAMS] (http://cams.seti.org/) and Skypatrol data. As the [Croatian Meteor Network] (http://cmn.rgn.hr/) grew in its demands, it became apparent that the existing solutions were not satisfactory.

**Features:**

1. view CAMS standard and Skypatrol standard image files in multiple filters
2. view reconstructed video from image files
3. make calibration (dark, flat) frames from meteor images
4. perform CAMS confirmation procedure

Latest Windows x86 build: https://dl.dropboxusercontent.com/u/7845267/HMM/CMN_binViewer_setup.exe

To build from source you will need:
- Python 2.7.8 or later
- wxPython3.0 or later
- scipy 0.14.0 or later
- numpy 1.8.2 or later
- PIL (Python Image Library) - Pillow-2.5.1 will do just fine

To make a Windows exe:
- cx_Freeze-4.3.2.win32-py2.7 or later

Build scripts are provided: setup.py and COMPILE_from_setup.bat (Windows only)
Making GIFs won't work on any other OS than windows, as the software relies on gifsicle.exe to compress GIF animations.

Copyright (c) 2014-2015, Denis Vida
* Reading FF*.bin files: based on Matlab scripts by Peter S. Gural
* images2gif: Copyright © 2012, Almar Klein, Ant1, Marius van Voorden
* gifsicle: Copyright © 1997-2013 Eddie Kohler

For academic use, please cite the paper:
>Vida D., Šegon D., Gural P. S., Martinović G., Skokić I., 2014, *CMN_ADAPT and CMN_binViewer software*, **Proceedings of the IMC, Giron, 2014**, 59 -- 63.
