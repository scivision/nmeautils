#!/usr/bin/env python3
'''
 Multithreaded NMEA serial port logger that allows logging every N seconds,
 even when GPS is giving data every second.
 Michael Hirsch
http://blogs.bu.edu/mhirsch
GPL v3+ license

An example of using non-blocking threading for serial port reading.
Note: python will be switching back and forth, processing one thread at a time.
This is just fine for thread(s) that sleep most of the time like here.
For parallel processing that bypasses the GIL, consider the multiprocessing module

tested in Python 2.7 and 3.4 with PySerial 2.7

REQUIRES PySerial, obtained via
 (linux)
 pip install pyserial
 or (windows with Anaconda)
 conda install pyserial
'''
from threading import Thread,Event
from serial import Serial
from time import sleep
from os.path import expanduser,splitext
from signal import signal, SIGINT
from datetime import date
from datetime import datetime as dt
from re import sub

def nmeapoll(sport,logfn,period,baud,verbose):

    nline = 4
    bytesWait = 500 #wait to read till this many bytes are in buffer

    # create a Serial object to manipulate the serial port
    hs = Serial(sport, baudrate=baud, timeout=1, bytesize=8,
                       parity='N', stopbits=1, xonxoff=0, rtscts=0)

    #is the serial port open? if not, open it
    if not hs.isOpen():
        print('opening port ' + hs.name)
        hs.open()

    #let's clear out any old junk
    hs.flushInput()
    hs.flushOutput()

    lastday = date.today()

    #start non-blocking read
    stop = Event()
    thread = Thread(target=portthread,
                    args=(hs,lastday,logfn,nline,verbose,bytesWait,period,stop))
    thread.start()

    # we put this after the thread so it knows how to stop the thread
    def signal_handler(*args):
        stop.set()
        print('\n *** Aborting program as per user pressed Ctrl+C ! \n')
        exit(0)
    signal(SIGINT,signal_handler)
    #silly printing to show we're not blocking
    while True:
        print('current time is ' + dt.utcnow().strftime('%H:%M:%S'))
        sleep(1)

def portthread(hs,lastday,logfn,nline,verbose,bytesWait,period,stop):
    # this loops waits for enough bytes in the buffer before proceeding
    while(not stop.is_set()):
        # now let next NMEA batch arrive
        inBufferByte = hs.inWaiting()
        if inBufferByte < bytesWait:
            if verbose:
               print(inBufferByte)
            stop.wait(0.5) #wait some more for buffer to fill (0.5 seconds)

            #check date
        else: # we have enough bytes to read the buffer
            readbuf(hs,lastday,logfn,nline,verbose)
            stop.wait(period-2.5) #empirical
            hs.flushInput()

def readbuf(hs,lastday,logfn,nline,verbose):
    Today = date.today()
    if (Today-lastday).days > 0:
        lastday = Today #rollover to the next day

    txt = []
    # get latest NMEA ASCII from Garmin
    for i in range(nline):
        line = hs.readline().decode('utf-8')
        if chksum_nmea(line):
            txt.append(line)

    #write results to disk
    cgrp=''.join(txt)
    if verbose:
        print(cgrp)

    if logfn is not None:
        stem,ext = expanduser(splitext(logfn))
        logfn = '{}-{}{}'.format(stem,lastday.strftime('%Y-%m-%d'),ext)
        with open(logfn,"a") as fid:
            fid.write(cgrp)
    elif not verbose:
        print(cgrp) #will print to screen if not already verbose


def chksum_nmea(sentence):
    '''
    from http://doschman.blogspot.com/2013/01/calculating-nmea-sentence-checksums.html
    '''
    # This is a string, will need to convert it to hex for
    # proper comparsion below
    cksum = sentence[-4:-2]

    # String slicing: Grabs all the characters
    # between '$' and '*' and nukes any lingering
    # newline or CRLF
    chksumdata = sub("(\n|\r\n)","", sentence[sentence.find("$")+1:sentence.find("*")])

    # Initializing our first XOR value
    csum = 0

    # For each char in chksumdata, XOR against the previous
    # XOR'd char.  The final XOR of the last char will be our
    # checksum to verify against the checksum we sliced off
    # the NMEA sentence

    for c in chksumdata:
        # XOR'ing value of csum against the next char in line
        # and storing the new XOR value in csum
        csum ^= ord(c)

    # Do we have a validated sentence?
    try:
        if hex(csum) == hex(int(cksum, 16)):
            return True
    except ValueError: #some truncated lines really mess up
        pass

    return False


if __name__ == '__main__':
    from argparse import ArgumentParser

    p = ArgumentParser(description='listens to Garmin NMEA')
    p.add_argument('-l','--log',help='specify log file to write GPS data to',type=str,default=None)
    p.add_argument('-p','--port',help='specify serial port to listen on',type=str,default='/dev/ttyS0')
    p.add_argument('-v','--verbose',help='print a lot of stuff to help debug',action='store_true')
    p.add_argument('-T','--period',help='polling period (default 10 seconds)',type=float,default=10)
    p.add_argument('-b','--baud',help='baud rate (default 19200)',type=int,default=19200)
    p = p.parse_args()

    nmeapoll(p.port, p.log, p.period, p.baud, p.verbose)
