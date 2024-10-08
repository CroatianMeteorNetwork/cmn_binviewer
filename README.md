# CMN_binViewer

CMN_binViewer -- view, organize, calibrate and confirm CAMS standard meteor data

CMN_binViewer came into existence during the second part of August 2014, as a result of a dire need of new viewing software for [CAMS](http://cams.seti.org/) and Skypatrol standard data. As the [Croatian Meteor Network](http://cmn.rgn.hr/) grew in its demands, it became apparent that the existing solutions were not satisfactory.

**Features:**

1. view RMS, CAMS standard and Skypatrol standard image files in multiple filters
2. view reconstructed video from .bin or .fits image files
3. make calibration (dark, flat) frames from .bin or .fits image files
4. perform RMS/CAMS confirmation procedure

**Installing Windows EXE**

Note: the installer will remove any existing version first. This is to avoid unexpected DLL errors 
due to updates in python or windows DLLs. 

Latest Windows builds: https://github.com/CroatianMeteorNetwork/cmn_binviewer/releases

Note that the 32-bit Windows package is legacy and unmaintained.

## Installing on Raspberry Pi

Run in terminal:

```
sudo apt-get update 
sudo apt-get install dpkg-dev build-essential libjpeg-dev libtiff-dev libsdl1.2-dev  libgstreamer-plugins-base0.10-dev libnotify-dev freeglut3 freeglut3-dev libwebkitgtk-dev libghc-gtk3-dev python-tk
```

Then clone this repository:
```
git clone https://github.com/CroatianMeteorNetwork/cmn_binviewer.git
```

Now create a virtual environment, activate it, and install the libraries:

```
virtualenv -p python3 ~/vBinviewer  
source ~/vBinviewer/bin/activate  
cd cmn_binviewer  
pip install -r requirements.txt  
```

Finally, enter the code directory activate your virtual environment and run the program:
```
cd cmn_binviewer  
source ~/vBinviewer/bin/activate  
python CMN_binViewer.py  

```

### Uprading

To upgrade on Windows, just download and install the latest package. 
To upgrade on Linux, Raspberry Pi or Mac, open a terminal window and type the following

```
cd ~/source/cmn_binviewer
git pull
```

### Potential issues:  

If python3 isn't available, you can try python2.7 instead when creating the virtualenv  
If you get an out of memory error while installing the libraries, use  
```
TMPDIR=~/tmp pip install -r requirements.txt  
```

## Installing using Anaconda (Windows, Linux or other platforms)

If you are using Anaconda:
First open a terminal, or a Windows command or powershell prompt then:

Create a virtual environment
```
conda create --name binviewer python=3
```

Then clone the repository:
```
git clone https://github.com/CroatianMeteorNetwork/cmn_binviewer.git
```

Activate the environment and install the libraries:

```
conda activate binviewer
pip install -r cmn_binviewer/requirements.txt
```

Then run the application :
```
cd cmn_binviewer
conda activate binviewer
python CMN_binViewer.py
```

## Installing on Fedora Linux

Tested on Fedora Linux 35.
Run in terminal:

```
sudo dnf install 'python3dist(astropy)' python3-pillow-tk 'python3dist(six)' 'python3dist(scipy)' 'python3dist(imageio)'
```

Then clone this repository:
```
git clone https://github.com/CroatianMeteorNetwork/cmn_binviewer.git
```

Then run the application :
```
cd cmn_binviewer
python3 CMN_binViewer.py
```

## Build scripts

Build scripts are provided for building a Windows exe - setup.py and COMPILE_from_setup.bat. 
To build under windows, create a suitable virtual environment and clone the repository as above,
then activate the virtualenv and run "COMPILE_from_setup.bat" or "python setup.py build"


Copyright (c) 2014-2015, Denis Vida
* Reading FF*.bin files: based on Matlab scripts by Peter S. Gural
* images2gif: Copyright © 2012, Almar Klein, Ant1, Marius van Voorden
* further contributions by Mark McIntyre, 2021


**Troubleshooting (Windows)**

If you are getting weird "Exception code is 0xc0000005 (access violation)" errors, it was reported that the ROBOFORM password manager conflicts with binViewer and causes this error. The solution was to disable the ROBOFORM program.


**Troubleshooting (Ubuntu/Debian)**

1. ImportError: cannot import name ImageTk:

Run:
```
sudo apt-get install python-imaging-tk
```

**Acknowledgements**

Many thanks to:

- **Damir Šegon** for support and suggestions 
- **Paul Roggermans** for thorough testing and objective criticism 
- **Peter S. Gural** for technical support
- **Mark McIntyre** for ongoing development

These are people without whom this software wouldn't be as half as good as it is today.

**Citations**

For academic use, please cite the paper:
>Vida D., Šegon D., Gural P. S., Martinović G., Skokić I., 2014, *CMN_ADAPT and CMN_binViewer software*, **Proceedings of the IMC, Giron, 2014**, 59 -- 63.
