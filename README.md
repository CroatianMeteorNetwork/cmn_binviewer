# CMN_binViewer

CMN_binViewer -- view, organize, calibrate and confirm CAMS standard meteor data

CMN_binViewer came into existence during the second part of August 2014, as a result of a dire need of new viewing software for [CAMS](http://cams.seti.org/) and Skypatrol standard data. As the [Croatian Meteor Network](http://cmn.rgn.hr/) grew in its demands, it became apparent that the existing solutions were not satisfactory.

**Features:**

1. view CAMS standard and Skypatrol standard image files in multiple filters
2. view reconstructed video from .bin image files
3. make calibration (dark, flat) frames from .bin image files
4. perform CAMS confirmation procedure

**Building**

Latest Windows x64 build (recommended): https://www.dropbox.com/s/44u5r9nso81wa56/CMN_binViewer_setup_x64.exe?dl=1

Latest Windows x86 build (legacy): https://www.dropbox.com/s/ygampv3b7xgxk74/CMN_binViewer_setup.exe?dl=1




To run or build from source you will need (take notice of the used versions):
- Python 2.7.8 or later (also tested on 2.7.9)
- wxPython 3.0.2.0
- scipy 0.14.0 (this version is strongly recommended, I also tested on 0.15.0 but it requires some tinkering with DLLs on Windows)
- numpy 1.8.2
- PIL (Python Image Library) - Pillow-2.5.1
- astropy
- imageio

To make a Windows exe:
- cx_Freeze-4.3.2.win32-py2.7

## Installing on Raspberry Pi

Run in terminal:

```
sudo apt-get update
sudo apt-get install dpkg-dev build-essential libjpeg-dev libtiff-dev libsdl1.2-dev libgstreamer-plugins-base0.10-dev libnotify-dev freeglut3 freeglut3-dev libwebkitgtk-dev libghc-gtk3-dev libwxgtk3.0-gtk3-dev
pip install wxPython
```

Then clone this repository:
```
git clone https://github.com/CroatianMeteorNetwork/cmn_binviewer.git
```

Finally, enter the code directory and run the program:
```
cd cmn_binviewer
python CMN_binViewer.py
```

## Installing using Anaconda

If you are using Anaconda, make sure to run binviewer in a Python 2 environment:
```
conda create --name binviewer python=2.7
```

Make sure to activate the environment every time before using it:

```
conda activate binviewer
```

And install the requirements:
```
conda install -y numpy scipy
conda install -y -c anaconda wxpython 
conda install -y astropy
conda install -y -c conda-forge pillow imageio
```


## Build scripts

Build scripts are provided: setup.py and COMPILE_from_setup.bat (Windows only). Making GIFs won't work on any other OS than Windows, as the software relies on gifsicle.exe to compress GIF animations.

Copyright (c) 2014-2015, Denis Vida
* Reading FF*.bin files: based on Matlab scripts by Peter S. Gural
* images2gif: Copyright © 2012, Almar Klein, Ant1, Marius van Voorden


**Troubleshooting (Windows)**

If you are getting weird "Exception code is 0xc0000005 (access violation)" errors, it was reported that the ROBOFORM password manager conflicts with binViewer and causes this error. The solution was to disable the ROBOFORM program.


**Troubleshooting (Ubuntu/Debian)**

1. ImportError: No module named wx:

Run:
```
sudo apt-get install python-wxgtk3.0
```

2. ImportError: cannot import name ImageTk:

Run:
```
sudo apt-get install python-imaging-tk
```

**Acknowledgements**

Many thanks to:

- **Damir Šegon** for support and suggestions 
- **Paul Roggermans** for thorough testing and objective criticism 
- **Peter S. Gural** for technical support

These are people without whom this software wouldn't be as half as good as it is today.

**Citations**

For academic use, please cite the paper:
>Vida D., Šegon D., Gural P. S., Martinović G., Skokić I., 2014, *CMN_ADAPT and CMN_binViewer software*, **Proceedings of the IMC, Giron, 2014**, 59 -- 63.
