import os
import datetime as dt

threshold=2 #minimum detections
mtp_original="MTPdetections_Original_Pre-Filtered.txt"
mtp_detections='MTPdetections.txt'
logfile='logfile.txt'
logsort='LOG_SORT.INF'

def logsort_date(date, provided=False):
    if provided:
        year, month, day, hour, minute, sec = date
    else:
        date=date.split(os.sep)
        if '' in date: 
            date.remove('')
        year, month, day, hour, minute, sec = map(int, date[-1].split('_'))

    today=dt.datetime(year, month, day, hour, minute, sec)
    
    if int(hour)<12:
        today-=dt.timedelta(hours=24)

    tomorrow=today+dt.timedelta(hours=24)

    return today.strftime('%Y%m%d')+tomorrow.strftime('%d')

def count(bmp, filter_list): #Counting the number of times a certain BMP appears on the list (used for detection threshold)
    z=0
    for line in filter_list:
        if line==bmp:
            z=z+1
    return z

def add_zero(num):
    if num>=10000:
        return str('%.3f' % num)
    if num>=1000:
        return '0'+str('%.3f' % num)
    if num>=100:
        return '00'+str('%.3f' % num)
    if num>=10:
        return '000'+str('%.3f' % num)
    return '0000'+str('%.3f' % num)

def add_zero_hms(num):
    if num>=10: 
        return str(num)
    return '0'+str(num)

def add_zero_ms(num):
    if num>=100: 
        return str(num)
    if num>=10: 
        return '0'+str(num)
    return '00'+str(num)

def sec2time(sec): #Seconds to hh:mm:ss:sss format
    hour=int(sec/3600)
    minute=int(sec/60)-hour*60
    second=int(sec)-minute*60-hour*3600
    msecond=int(str('%.3f' % sec).split('.')[1])
    return add_zero_hms(hour)+':'+add_zero_hms(minute)+':'+add_zero_hms(second)+':'+add_zero_ms(msecond)

def stop_time(bmp, logfile_list_stop): #Getting stop time from logfile for particular BMP
    for line in logfile_list_stop:
        if 'stop' in line and bmp in line:
            return line.split()[4]

def mtp2detected(directory, date=None): #Function for making fake detected files (logsorts and such)
    if date is not None:
        date = logsort_date(date, provided = True)
    else:
        date=logsort_date(directory)
    os.chdir(directory)
    if os.path.isfile(logfile):
        if os.path.isfile(mtp_detections):

            z=0
            ll=0

            logfile_list_stop=[]
            mtp_detections_list=[]
            logsort_list=[]
            filter_list=[]
            logsort_filtered=[]
            #bmp_list=[]
            for line in open(logfile): #Reading logfile
                if z==0:
                    logfile_line1=line #Exposure line
                    z=z+1
                    continue
                if z==1:
                    logfile_line2=line #Framerate line
                    z=z+1
                    continue
                if 'stop' in line:
                    logfile_list_stop.append(line)

            for line in open(mtp_detections): #Reading MTP_detections
                if ll<2:
                    ll=ll+1
                    continue
                mtp_detections_list.append(line)
                
            # try:
            #    exptime=float(logfile_line1.split(':')[1]) #Getting exp time
            # except:
            #    print('Error in logfile!!!')
            #    return False
            
            for event in mtp_detections_list:

                event=event.split()
                # mtp_image=int(event[1][2:])
                mtp_frame=float(event[2]) #Changed from int!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
                try:
                    fsec=stop_time(event[1][2:], logfile_list_stop).split(':')
                except:
                    continue
                
                fsec=float(fsec[0])*3600+float(fsec[1])*60+float(fsec[2])+float(fsec[3])/1000

                #fsec=fsec-(1500*exptime-(mtp_frame-3))*0.04 #OLD
                #T_det=BMP_sss[BMP]-0.04*(256-Frame_No); #C++ NEW

                fsec=fsec-0.04*(256-mtp_frame) #Maybe (mtp_frame-3) ?

                if fsec<0: 
                    fsec=fsec+86400 #If stop time is after midnight, and meteor frames before, we need to add a day of seconds (otherwise the seconds would go to minus)

                logsort_line=event[0]+' '+event[2]+' '+sec2time(fsec)+' '+add_zero(fsec)+' '+event[1]+' '+'00'+' '+'000'+' '+event[3]+' '+event[4]+' '+event[5]
                logsort_list.append(logsort_line)

            for line in logsort_list: #Stripping BMP numbers from the list and putting them to a separate list
                line=line.split()
                filter_list.append(line[4])

            for line in logsort_list:
                check=line.split()
                if count(check[4], filter_list)>threshold: #Min. number of detections filter
                    logsort_filtered.append(line)
                    
            #date=os.path.basename(os.path.abspath('.')) #Getting date from folder name
            newfile=open(logsort, 'w')
            newfile.write('Date: '+date[0:4]+' '+date[4:6]+' '+date[6:8]+' '+date[8:10]+'\n')
            newfile.write('UT_corr: 0'+'\n'+'Type: SORTED'+'\n')
            newfile.write(logfile_line1)
            newfile.write(logfile_line2)
            for line in logsort_filtered:
                newfile.write(line+'\n')
            newfile.write('999')
            newfile.close()

            return True

#mtp2detected('.\\2014_04_22_20_09_18\\')
