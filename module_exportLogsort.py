from __future__ import print_function
import os
import shutil
import errno
import datetime
from module_CAMS2CMN import run_cams2cmn
from module_MTP2logsort import mtp2detected

logsort_name = 'LOG_SORT.INF'
capturestats_name = 'CaptureStats.log'
capturestats_dict_name = 'CaptureStats_logfile.txt'

def mkdir_p(path):
    """ Makes a directory and handles all errors.
    """
    try:
        os.makedirs(path)
    except OSError as exc:
        if exc.errno == errno.EEXIST:
            pass
        else: raise

def _makeCAMS2CMNdict(dir_path):
    """ Returns a dictionary of names of converted FFbin files to fake Skypatrol C_ files.
    """

    dict_path = dir_path+capturestats_dict_name

    if not os.path.exists(dict_path):
        print('No '+capturestats_dict_name+' found!')
        return False

    cams2cmn_dict = {}
    for line in open(dict_path).readlines():
        line = line.replace('\n', '').split()

        ff_bin = line[3]
        c_file = line[0]

        cams2cmn_dict[ff_bin] = c_file

    return cams2cmn_dict

def _getLogsortLines(dir_path, cams2cmn_dict, ff_bin, met_no):
    """ Returns logsort lines of given meteor.
    """
    if cams2cmn_dict != None:
        # CAMS
        c_file = 'C_'+cams2cmn_dict[ff_bin]
    else:
        # Skypatrol
        c_file = 'C_'+ff_bin.split('.')[0]

    met_no = str(met_no).zfill(4)

    logsort_list = []

    for line in open(dir_path+logsort_name).readlines()[5:]:
        if (line =='999') or (line == '999\n'):
            break
        line = line.split()

        met_no_line = line[0]
        c_file_line = line[4]

        if (c_file == c_file_line) and (met_no == met_no_line):
            logsort_list.append(line)

    return logsort_list

def _getRecordDate(capturestats_path):
    """ Returns a tuple containing date and time of recording start from CaptureStats.log file.
    """
    capturestats_file = open(capturestats_path).readlines()

    for line in capturestats_file:
        if 'Start Time =' in line:
            break

    line = line.split()

    month, date, year = map(int, line[3].split('/'))
    hour, minute = map(int, line[4].split(':'))

    return (year, month, date, hour, minute, 0)


def exportLogsort(dir_source, dir_dest, data_type, ff_bin, met_no, start_frame, end_frame, fps, image_list):
    """ Export LOG_SORT.INF file from FTPdetectinfo for fireball analysis.
    """

    # Find required files for processing
    FTPdetect_status = False
    FTPdetect_name = None

    captured_stats_status = False

    logfile_status = False
    logfile_name = 'logfile.txt'

    for line in os.listdir(dir_source):
        if ('FTPdetectinfo' in line) and (not 'original' in line):
            FTPdetect_status = True
            FTPdetect_name = line

        if line == capturestats_name:
            captured_stats_status = True

        if line == logfile_name:
            logfile_status = True


    if FTPdetect_status and captured_stats_status and ((data_type == 1) or (data_type == 3)):
        # CAMS processinig

        mkdir_p(dir_dest)
        shutil.copy2(dir_source + FTPdetect_name, dir_dest + FTPdetect_name)
        shutil.copy2(dir_source + capturestats_name, dir_dest + capturestats_name)


        # Convert CAMS format to CMN format
        run_cams2cmn(dir_dest, 6, skip_calstars = True)

        # Convert MTPdetections to LOG_SORT.INF
        print('Converting MTPdetections to LOG_SORT.INF...')
        mtp2detected(dir_dest, date = _getRecordDate(dir_dest + capturestats_name))
        print('Done!')

        cams2cmn_dict = _makeCAMS2CMNdict(dir_dest)

        if cams2cmn_dict == False:
            return False

        logsort_list = _getLogsortLines(dir_dest, cams2cmn_dict, ff_bin, met_no)

    elif logfile_status and (data_type == 2):
        # Skypatrol processing

        # Make output directory and copy logsort into it
        mkdir_p(dir_dest)
        shutil.copy2(dir_source + logsort_name, dir_dest + logsort_name)

        logsort_list = _getLogsortLines(dir_dest, None, ff_bin, met_no)
        
    else:
        # No required files found
        return False

    logsort_list = _adjustLogsort(logsort_list, fps, start_frame = start_frame, end_frame = end_frame)

    if logsort_list == False:
        # GENERIC LOGSORT!
        pass

    logsort_list = _replaceImages(logsort_list, image_list)

    # Write logsort changes to LOG_SORT.inf file
    replaceLogsort(logsort_list, dir_dest+logsort_name)

    return True



def replaceLogsort(logsort_list, logsort_path, header=None):
    """ Write logsort list to a LOG_SORT.INF file.
    """
    if os.path.exists(logsort_path):
        if header == None:
            # Read header from old logsort
            old_logsort_header = open(logsort_path).readlines()[:5]
        else:
            old_logsort_header = header

        # Open new logsort
        newfile = open(logsort_path, 'w')

        # Write old header to new logsort
        for line in old_logsort_header:
            newfile.write(line)

        # Write new logsort data
        for line in logsort_list:
            newfile.write(" ".join(line)+'\n')

        newfile.write('999')
        newfile.close()

def _replaceImages(logsort_list, image_list):
    """ Replaces images from logsort with ones provided in the list.
    """

    if len(logsort_list) == len(image_list):

        new_logsort = []
        for i, line in enumerate(logsort_list):
            new_logsort.append(line[:4] + [image_list[i]] + line[5:])

        return new_logsort

    else:
        # Lists don't match!
        return False



def _adjustLogsort(logsort_list, fps, start_frame, end_frame):
    """ Adjusts frame number according to the given start and end frames, and replaces logsort image with given image names.
    """

    def _getTime(time):
        """ Returns datetime object from given format: HH:MM:SS:sss
        """
        hour, minute, sec, msec = map(int, time.split(':'))

        return datetime.datetime(year = 1970, month = 1, day = 1, hour = hour, minute = minute, second = sec, microsecond = msec*1000)

    def _formatTime(time):
        """ Returns formated string from datetime object in: HH:MM:SS:sss
        """
        return ":".join([str(time.hour).zfill(2), str(time.minute).zfill(2), str(time.second).zfill(2), str(time.microsecond/1000).zfill(3)])

    def _formatLogsortLine(met_no, frame, extend_time, julian_time):
        """ Returns one line in logsort format, by given parameters.
        """
        return [met_no, str(round(frame, 1)).zfill(6), extend_time, julian_time.zfill(9), "C_00000000", "00", "000", str(round(fill_x, 2)).zfill(6), str(round(fill_y, 2)).zfill(6), "000100"]



    julian_diff = 0.02 # For interlaced frames

    # Starting coordinates for filling missing frames
    fill_x = 100.0
    fill_y = 100.0

    # Detect frame deinterlace
    if len(logsort_list) >= 2:
        frame_diff = abs(float(logsort_list[0][1]) - float(logsort_list[1][1]))

        if frame_diff % 1 != 0:
            interlaced = True
        else:
            interlaced = False

    else:
        # Too little frames for detection-based logsort, use the generic one!
        print('Too little frames for detection-based logsort, use the generic one!')
        return False

    time_difference = 1.0 / (fps * ((int(interlaced) + 1)))
    time_difference = datetime.timedelta(seconds = time_difference)

    # Generate a list of frames to be written
    if interlaced:
        frame_list = range(start_frame*2, end_frame*2 + 2)
        frame_list = map(float, frame_list)
        frame_list = [x/2 for x in frame_list]
    else:
        julian_diff = julian_diff * 2
        frame_list = range(start_frame, end_frame + 1)

    met_no = logsort_list[0][0]
    first_frame = float(logsort_list[0][1])
    first_time = _getTime(logsort_list[0][2])
    first_julian = float(logsort_list[0][3])

    last_frame = float(logsort_list[-1][1])
    last_time = _getTime(logsort_list[-1][2])
    last_julian = float(logsort_list[-1][3])

    # Cut or extand the beggining of a logsort list, according to the start frame
    if first_frame < frame_list[0]:
        # Cut beggining

        start_pointer = 0

        for line in logsort_list:

            if float(line[1]) >= frame_list[0]:
                break

            start_pointer += 1

        logsort_list = logsort_list[start_pointer:]



    elif first_frame > frame_list[0]:
        # Extend beggining

        frame_extend = []

        for frame in frame_list:
            if float(logsort_list[0][1]) == frame:
                break

            frame_extend.append(frame)

        extend_logsort_list = []
        for i, ext_frame in enumerate(reversed(frame_extend)):

            extend_time = _formatTime(first_time - (i+1) * time_difference)
            julian_time = str(first_julian - (i+1) * julian_diff)
            extend_line = _formatLogsortLine(met_no, ext_frame, extend_time, julian_time)
            #fill_x += 1
            #fill_y += 1
            extend_logsort_list.append(extend_line)

        extend_logsort_list = extend_logsort_list[::-1]

        logsort_list = extend_logsort_list + logsort_list


    # Cut or extand the end of a logsort list, according to the end frame
    if last_frame > frame_list[-1]:
        # Cut ending

        end_pointer = 0

        for line in logsort_list:

            if float(line[1]) >= frame_list[-1]:
                break

            end_pointer += 1

        logsort_list = logsort_list[:end_pointer+1]

    elif last_frame < frame_list[-1]:
        # Extend ending

        frame_extend = []

        for frame in reversed(frame_list):
            if float(logsort_list[-1][1]) == frame:
                break

            frame_extend.append(frame)

        frame_extend = frame_extend[::-1]

        extend_logsort_list = []
        for i, ext_frame in enumerate(frame_extend):

            extend_time = _formatTime(last_time + (i+1) * time_difference)
            julian_time = str(last_julian + (i+1) * julian_diff)
            extend_line = _formatLogsortLine(met_no, ext_frame, extend_time, julian_time)
            #fill_x += 1
            #fill_y += 1
            extend_logsort_list.append(extend_line)

        logsort_list = logsort_list + extend_logsort_list

    # Fill missing frames
    for i, frame in enumerate(frame_list):

        if float(logsort_list[i][1]) == frame:

            previous_time = _getTime(logsort_list[i][2])
            previous_julian = float(logsort_list[i][3])

        else:
            fill_time = _formatTime(previous_time + time_difference)
            fill_julian = str(round(previous_julian + julian_diff, 3))

            new_line = _formatLogsortLine(met_no, frame, fill_time, fill_julian)
            logsort_list.insert(i, new_line)

            previous_time = _getTime(fill_time)
            previous_julian = float(fill_julian)

        
    return logsort_list

def genericLogsort():
    """ Generates a generic LOG_SORT.INF with placeholder positions.
    """
    pass


def postAnalysisFix(logsort_path, data_type):
    """ Fixes logsort after analysis with CMN_FBA.
    """
    def _fixDoubleHeader(logsort_list):
        """ Detects and removed double header produced by CMN_FBA.
        """

        double_header = False

        first_line = logsort_list[0]
        count = 0
        for line in logsort_list[1:]:
            count += 1
            if line == first_line:
                double_header = True
                break

        if double_header:
            logsort_list = logsort_list[count:]
            header = logsort_list[:count]
        else:
            header = logsort_list[:5]
        
        logsort_list = logsort_list[5:]

        return header, logsort_list

    # Load logsort content
    try:
        logsort_list = open(logsort_path).readlines()
    except:
        return False


    # FBA can produce double header, fix that
    header, logsort_list = _fixDoubleHeader(logsort_list)

    # Save fixed logsort
    replaceLogsort([line.split() for line in logsort_list], logsort_path, header = header)

    if (data_type == 1) or (data_type == 3):

        # CAMS processing
        # Make a dictionary for a link between FF*.bin files and fake C_ files
        parent_path = os.path.normpath(os.path.join(logsort_path, "..")) + os.sep
        CAMS2CMNdict = _makeCAMS2CMNdict(parent_path)
        
        if CAMS2CMNdict == False:
            return False

    image_list = []
    logsort_split_list = []
    for line in logsort_list:
        if (line == '999') or (line == '999\n'):
            break

        line = line.split()

        logsort_split_list.append(line)

        if data_type == 1:

            # CAMS processing
            image = line[4].split('_frame')[0]+'.bin'
            image_list.append('C_'+CAMS2CMNdict[image])

        elif data_type == 2:
            # Skypatrol processing
            image = line[4].split('_frame')[0]+'.bmp'
            image_list.append('C_'+image)

        elif data_type == 3:

            # RMS processing
            image = line[4].split('_frame')[0] + '.fits'
            image_list.append('C_' + CAMS2CMNdict[image])

    logsort_list = _replaceImages(logsort_split_list, image_list)

    # Rename LOG_SORT used with FBA
    shutil.copy(logsort_path, '.'.join(logsort_path.split('.')[:-1])+'_FBA.inf')

    replaceLogsort(logsort_list, logsort_path, header = header)

        


#exportLogsort("C:\\Users\\Administrator\\Desktop\\logsort_extract\\2014_08_19_00_30_28\\", 
#    "C:\\Users\\Administrator\\Desktop\\logsort_extract\\2014_08_19_00_30_28\\fireball_example\\", 'FF451_20140818_214533_437_0140032.bin', 5, 190, 210, 25, map(str, range(0, 42)))

#postAnalysisFix("C:\\Users\\Administrator\\Desktop\\fb_test\\LOG_SORT.INF")
