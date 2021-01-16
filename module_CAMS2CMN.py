# CAMS to CMN converter
# v1.0 2014-04-15 by I. Skokic, Croatian Meteor Network
# based on Delphi CAMS2CMN software
# python 3 (works also with python 2.6 or higher)

from __future__ import print_function  # for compatibility python 2/3
import sys
import os.path
from datetime import datetime, timedelta



def create_paired_file(cams_cap_stats_file, cmn_log_file):
    print('Converting ' + cams_cap_stats_file + ' to ' + cmn_log_file + '... ', end = '')
    CAMS_FF_STR = ' FF file written for '
    paired_file = os.path.join(os.path.dirname(cams_cap_stats_file), 'CaptureStats_logfile.txt')
    f_cams = open(cams_cap_stats_file, 'r')
    f_cmn = open(cmn_log_file, 'w')
    f_paired = open(paired_file, 'w')
    f_cmn.write('Exposure time       : 0.1706666667\n')
    f_cmn.write('Framerate           : 25\n')
    i = 0
    paired = []
    first_date = 0
    for line in f_cams:
        p = line.find(CAMS_FF_STR)
        if p>0:
            i = i + 1
            dt = line[0:p]            
            tm = dt[-12:]
            fn = line[p+len(CAMS_FF_STR):-1].strip()
            fns = fn.split('_')
            try:
                date_taken = datetime.strptime(fns[1]+' '+fns[2]+'.'+fns[3],'%Y%m%d %H%M%S.%f')
                date_taken = date_taken + timedelta(seconds=10.24) #add 10.24 s to correct the time                
                if i == 1: 
                    first_date = date_taken
                dt = datetime.strftime(date_taken,'%Y-%m-%d %H:%M:%S.%f')[:-3]
                tm = datetime.strftime(date_taken,'%H:%M:%S:%f')[:-3]
                f_paired.write('%08d %s %s\n' % (i,dt,fn))
                f_cmn.write('! stop recording %08d %s\n' % (i,tm))
                paired.append(fn)
            except ValueError:
                date_taken = -1
                print('\nWarning: can\'t convert date from '+fn+' in '+cams_cap_stats_file,'.')
    f_cmn.write('999\n')
    f_cams.close()
    f_cmn.close()
    f_paired.close()
    print('done!')
    return paired, first_date


    
def convert_cal_stars(cams_cal_stars_file, cmn_cal_stars_file, paired_data, use_every_nth):
    print('Converting ' + cams_cal_stars_file + ' to ' + cmn_cal_stars_file + '... ', end = '')
    f_cams = open(cams_cal_stars_file, 'r')
    f_cmn = open(cmn_cal_stars_file, 'w')
    f_cmn.write('Processed with CAMS2CMN on '+datetime.strftime(datetime.now(),'%a %b %d %H:%M:%S %Y')+'\n')
    f_cmn.write('-------------------------------------------------\n')
    frame_cnt = 0
    if use_every_nth<=0:
        use_every_nth = 1
    search_paired = True
    for line in f_cams:
        if search_paired:
            p = [i for i, s in enumerate(paired_data) if line.find(s)>=0] # find line in paired_data
            if len(p)>0:                
                frame_cnt = frame_cnt + 1
                cnt = 0
                search_paired = False                
        else:            
            l = line.strip().split()
            if (len(l)==4 and line.find('Integ pixels')<0):
                values = []
                for v in l:                    
                    try:
                        values.append(float(v))
                    except ValueError:
                        values = []       
                if len(values)==4:
                    cnt = cnt + 1
                    if ((frame_cnt-1) % use_every_nth == 0):
                        f_cmn.write('%03d C_%08d %06d %08.2f %08.2f\n' % (cnt,p[0]+1,values[2],values[1],values[0]))
            elif (line.find('Integ pixels')<0 and line.find('Star area')<0):
                search_paired = True
    f_cams.close()
    f_cmn.close()
    print('done!')




def convert_ftp_detec(cams_ftp_detec_file, cmn_mtp_detec_file, switch_fields, paired_data, date_taken):
    print('Converting ' + cams_ftp_detec_file + ' to ' + cmn_mtp_detec_file + '... ', end = '')
    f_cams = open(cams_ftp_detec_file, 'r')
    f_cmn = open(cmn_mtp_detec_file, 'w')
    if isinstance(date_taken, datetime):
        f_cmn.write('Captured with CAMS on '+datetime.strftime(date_taken,'%Y %m %d %H:%M:%S %Y')+'\n')
    else:
        f_cmn.write('Processed with CAMS2CMN on '+datetime.strftime(datetime.now(),'%a %b %d %H:%M:%S %Y')+'\n')
    f_cmn.write('-------------------------------------------------\n')
    search_paired = True
    header_found = False
    prev_l = []
    header = []
    total = -1
    curr_file = ''
    count = 0
    # field = -1  # variable not used
    for line in f_cams:
        if search_paired:
            p = [i for i, s in enumerate(paired_data) if line.find(s)>=0] # find line in paired_data
            if len(p)>0:                
                prev_l = []
                curr_file = line[:-1]
                search_paired = False
                count = 0
        else:            
            l = line.strip().split()
            if len(l)==10:
                header = l
                header_found = True
                try:
                    total = int(header[2])
                except ValueError:
                    total = -1                    
            elif (len(l)==8 and header_found):
                count = count + 1
                if len(prev_l)==8:
                    try:
                        prev_field = float(prev_l[0])
                        curr_field = float(l[0])
                        found_two_fields = int(prev_field)==int(curr_field)
                    except ValueError:
                        found_two_fields = False
                    if switch_fields and found_two_fields:
                        f_cmn.write('%s C_%.08d %s %s %s %s %s %s %s\n' % (header[1],p[0]+1,prev_l[0],l[1],l[2],prev_l[7],header[7],header[8],header[9]))
                        f_cmn.write('%s C_%.08d %s %s %s %s %s %s %s\n' % (header[1],p[0]+1,l[0],prev_l[1],prev_l[2],l[7],header[7],header[8],header[9]))
                        prev_l = []
                    else:
                        f_cmn.write('%s C_%.08d %s %s %s %s %s %s %s\n' % (header[1],p[0]+1,prev_l[0],prev_l[1],prev_l[2],prev_l[7],header[7],header[8],header[9]))
                        prev_l = l
                else:
                    prev_l = l                        
            elif (line.find('Uncalibrated')<0):
                if len(prev_l)==8: 
                    f_cmn.write('%s C_%.08d %s %s %s %s %s %s %s\n' % (header[1],p[0]+1,prev_l[0],prev_l[1],prev_l[2],prev_l[7],header[7],header[8],header[9]))
                prev_l = []
                if header_found and (total>=0) and (count!=total):
                    print('\nWarning: event count different from specified for '+curr_file+' in ',cams_ftp_detec_file+'')
                search_paired = True
                header_found = False                
    if len(prev_l)==8: 
        f_cmn.write('%s C_%.08d %s %s %s %s %s %s %s\n' % (header[1],p[0]+1,prev_l[0],prev_l[1],prev_l[2],prev_l[7],header[7],header[8],header[9]))
    f_cams.close()
    f_cmn.close()    
    print('done!')
    

def convert_rmsftp_to_cams(ftpdata, cams_code, cal_file_name):
    camsdata=ftpdata

    lc = len(camsdata)
    for i in range(lc):
        if i == lc:
            break

        # skip the header lines
        if i < 11:
            continue

        # replace RMS code with CAMS code, and replace the recalibration line with the CAMS CAL filename
        if camsdata[i][:3] == '---' and i < lc:
            splits = camsdata[i+1].split('_')
            rmscode = splits[1]
            camsdata[i+1] = camsdata[i+1].replace(rmscode, cams_code).replace('.fits', '.bin')
            camsdata[i+2]=cal_file_name + '\n'
            camsdata[i+3] = camsdata[i+3].replace(rmscode, cams_code)

    return camsdata


def main():
    print('CAMS2CMN v1.0.0 (python version)')
    num_args = len(sys.argv)
    if num_args >= 4:
        switch_fields = False
        use_every_nth = 1
        cams_cap_stats_file = sys.argv[1]
        cams_cal_stars_file = sys.argv[2]
        cams_ftp_detec_file = sys.argv[3]
        cmn_log_file = os.path.join(os.path.dirname(cams_cap_stats_file), 'logfile.txt')
        cmn_cal_stars_file = os.path.join(os.path.dirname(cams_cal_stars_file), 'CalibrationStars.txt')
        cmn_mtp_detec_file = os.path.join(os.path.dirname(cams_ftp_detec_file), 'MTPdetections.txt')
        if num_args >= 5:
            try:
                use_every_nth = int(sys.argv[4])
            except ValueError:
                use_every_nth = 1
            switch_fields = sys.argv[4] == '/S'    
            if num_args > 5:    
                switch_fields = sys.argv[5] == '/S'
        if not os.path.exists(cams_cap_stats_file):
            print('Error: can\'t find file ' + cams_cap_stats_file + '. Exiting.')
        elif not os.path.exists(cams_cal_stars_file):
            print('Error: can\'t find file ' + cams_cal_stars_file + '. Exiting.')
        elif not os.path.exists(cams_ftp_detec_file):
            print('Error: can\'t find file ' + cams_ftp_detec_file + '. Exiting.')
        else:    
            paired_data, date_taken = create_paired_file(cams_cap_stats_file, cmn_log_file)
            convert_cal_stars(cams_cal_stars_file, cmn_cal_stars_file, paired_data, use_every_nth)
            convert_ftp_detec(cams_ftp_detec_file, cmn_mtp_detec_file, switch_fields, paired_data, date_taken)
    else:
        print()
        print('Usage: CAMS2CMN CaptureStats CalStars FTPdetectinfo [N] [/S]')
        print()
        print('Convert CAMS files to CMN format.')
        print()
        print('Arguments:')
        print('  CaptureStats    path to CaptureStats file')
        print('  CalStars        path to CalStars file')
        print('  FTPdetectinfo   path to FTPdetectinfo file')
        print()
        print('Optional arguments:')
        print('  N    use every Nth frame from CalStars_file, default=1 (every frame)')
        print('  /S   switch even/odd fields in MTPdetections.txt')
         
##if __name__ == '__main__':
##           main()


def run_cams2cmn(date, use_every_nth=1, skip_calstars = False):
    
    switch_fields=False
    
    #path='C:\\HMM_ADAPT\\CAMS\\ArchivedFiles\\'
    #date=path+'2014_04_21_18_27_39'+'\\'
    calstars_file=''
    detect_file=''
    for line in os.listdir(date):
        if 'CALSTARS' in line:
            calstars_file=line
        if ('FTPdetectinfo_' in line) and ('original' not in line):
            detect_file=line

    if skip_calstars is True:
        calstars_file = ' '

    if calstars_file=='' or detect_file=='':
        return False

    cams_cap_stats_file = date+'CaptureStats.log'
    if not skip_calstars:
        cams_cal_stars_file = date+calstars_file
    cams_ftp_detec_file = date+detect_file
    
    cmn_log_file = os.path.join(os.path.dirname(cams_cap_stats_file), 'logfile.txt')
    if not skip_calstars:
        cmn_cal_stars_file = os.path.join(os.path.dirname(cams_cal_stars_file), 'CalibrationStars.txt')
    cmn_mtp_detec_file = os.path.join(os.path.dirname(cams_ftp_detec_file), 'MTPdetections.txt')
    
    paired_data, date_taken = create_paired_file(cams_cap_stats_file, cmn_log_file)
    if not skip_calstars:
        convert_cal_stars(cams_cal_stars_file, cmn_cal_stars_file, paired_data, use_every_nth)
    convert_ftp_detec(cams_ftp_detec_file, cmn_mtp_detec_file, switch_fields, paired_data, date_taken)

    return True


#run_cams2cmn("C:\\HMM_ADAPT\\CAMS\\CapturedFiles\\2014_04_22_20_33_28\\")
