CMN Binviewer Change Log
========================
3.36.2
Mar 24: bugfix in shower detection in Detected mode. 
        Remove deprecation warning in Pillow.
        
3.36.1
Sep 23: Bugfix in frame extraction.

3.36.0
Sep 23: Hotkey "R" to display the radiant map if available.
        Hotkey "C" to start confirmation.
        Upgrade gifsicle to 1.94.
        Bugfix in gif-generation.
        Bugfix in review of rejected files.
        View logfiles from within the app.

3.35.1
Aug 23: bugfix for crash on Windows11 due to numpy float deprecation

3.35
Jun 23: in detection or confirmation mode, show mag and shower if known, and include on saved images. 
        Add new mode to display images filtered out by the ML. Requires the rejected FITS files to be in either
        ArchivedFiles or CapturedFiles. 

3.34 
Nov 2021: save-frames was saving in parent of chosen folder

3.33
Oct 2021: fix black-button bug on Pi

3.32    
Sep 2021: Add menu option to enable/disable collection of 
RejectedFiles.

3.31    
May 2021: Support for 50fps as well as 25 and 30. To 
change fps, use the box in the Animation frame.
Create default config file if not present.
Enable/disable collection of RejectedFiles (requires edit 
of config.ini)

3.30    
Apr 2021: Support passing of ftpfile on the commandline 
(request from TammoJan)

3.24    
Apr 2021: workaround bug in CSV file 
(invalid time if secs > 59.00)   

3.23:   
Mar 2021: various small bugfixes.

3.22:   
Mar 2021: handle nonstandard source folder names better.

3.21    
Mar 2021: filter duplicate data from the ftpfile, if present. 

3.20    
Feb 2021: Video mode now supported again. 

3.10    
Jan 2021: Multiple bugfixes and python2 compatability fixes. 

3.00    
Jan 2021: Disable video as it hangs on Python3. 
Make config file writable

2.57:   
2020: Multiple Python3 and requirements updates to the codebase
Add ability to save rejected files.
Simplifcation of some parts of the code. 
Other bugfixes resolved. 
        
