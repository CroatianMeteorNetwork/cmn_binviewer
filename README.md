# CMN_binViewer

CMN_binViewer -- view, organize, calibrate and confirm CAMS standard meteor data

CMN_binViewer came into existence during the second part of August 2014, as a result of a dire need of new viewing software for [CAMS](http://cams.seti.org/) and Skypatrol standard data. As the [Croatian Meteor Network](http://cmn.rgn.hr/) grew in its demands, it became apparent that the existing solutions were not satisfactory.

**Features:**

1. view RMS, CAMS standard and Skypatrol standard image files in multiple filters
2. view reconstructed video from .bin or .fits image files
3. make calibration (dark, flat) frames from .bin or .fits image files
4. perform RMS/CAMS confirmation procedure

**Installing Windows EXE**

NB: you must uninstall any existing version before installing the new version. Otherwise you may get
unexpected DLL errors ! 

Latest Windows x64 build (recommended): https://www.dropbox.com/s/4eutahlxojrkvsa/CMN_binViewer-setup64.exe?dl=0

Latest Windows x86 build (legacy): https://www.dropbox.com/s/o6jn1ecsl7trdxk/CMN_binViewer-setup32.exe?dl=0


## Installing on Raspberry Pi

Run in terminal:

```
sudo apt-get update
sudo apt-get install dpkg-dev build-essential libjpeg-dev libtiff-dev libsdl1.2-dev libgstreamer-plugins-base0.10-dev libnotify-dev freeglut3 freeglut3-dev libwebkitgtk-dev libghc-gtk3-dev libwxgtk3.0-gtk3-dev

Then clone this repository:
```
git clone https://github.com/CroatianMeteorNetwork/cmn_binviewer.git
```

Now create a virtual environment, activate it, and install the libraries:
---
virtualenv -p python3 ~/vBinviewer
source ~/vBinviewer/bin/activate
cd cmn_binviewer
pip -y install -r requirements.txt
```

Finally, enter the code directory activate your virtual environment and run the program:
```
cd cmn_binviewer
source ~/vBinviewer/bin/activate
python CMN_binViewer.py

```
Potential issues: 
If python3 isn't available, you can try python2.7 instead when creating the virtualenv
If you get an out of memory error while installing the libraries, use
TMPDIR=~/tmp pip -y install -r requirements.txt


## Installing using Anaconda (Windows, Linux or other platforms)

If you are using Anaconda:
First open a terminal, or a Windows command or powershell prompt then:

Create a virtual environment
```
conda create --name binviewer python=3

```
Then clone this repository:
```
git clone https://github.com/CroatianMeteorNetwork/cmn_binviewer.git

--- 

Activate the environment and install the libraries:

```
conda activate binviewer
pip install -y -r cmn_binviewer/requirements.txt
```
Then run the application :
---
cd cmn_binviewer
conda activate binviewer
python CMN_binViewer.py


## Build scripts

Build scripts are provided for building a Windows exe - setup.py and COMPILE_from_setup.bat. 
To build under windows, create a suitable virtual environment and clone the repository as above,
then activate the virtualenv and run "COMPILE_from_setup.bat"


Copyright (c) 2014-2015, Denis Vida
* Reading FF*.bin files: based on Matlab scripts by Peter S. Gural
* images2gif: Copyright © 2012, Almar Klein, Ant1, Marius van Voorden
* further contributions by Mark McIntyre, 2021


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
