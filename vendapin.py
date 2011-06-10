#!/sw/bin/python2.6
# -*- coding: utf-8 -*-
#
# module to support the Vendapin serial protocol
# http://www.vendapin.com/Adobe%20files/CTD202-203_API.pdf
#

import sys
import serial
import time


# packet breakdown:
# <STX><ADD><CMD><LEN><DTA><ETX><CHK>
#
STX = 0x02  # Start of Text Data
# CMD - Command Code Byte (0x80-0xFF)
# LEN - Length of Data - Byte Size (0x00 or higher)
# DTA Packet Data (Optional, leave empty if not used)
ADD = 0x01  # Device Address (Set to 0x01 if not used)
ETX = 0x03  # End of Text Data
# CHK - XOR Checksum of data packet

PACKET_MIN = 5 # the maximum packet length
PACKET_MAX = 128 # the maximum packet length

# commands
ENABLE = 0xFE   # Enable VCB-2 Motor Control (Default at start-up)
DISABLE = 0xFF  # Disable VCB-2 Motor Control
RESERVED = 0xF0 # Reserved - for Factory use only

DISPENSE = 0x80            # Dispense Card - no data
REQUEST_STATUS = 0x81      # Request Status - no data
READ_TOTAL_COUNT = 0x82    # Read Total Dispense Count Meter (count after API command is sent)
READ_TOTAL_BUTTON_COUNT = 0x83  # Read Total Dispense Button Count Meter (count after Dispense button is used)
WRITE_TOTAL_RETRIES = 0x84 # Write Total Number of Retries
READ_TOTAL_RETRIES = 0x85  # Read Total Number of Retries
RESET_SETTINGS = 0x86      # Reset the card dispenser settings - no data or 1 byte unsigned CHAR
WRITE_CARD_HOLD = 0x87     # Write “Hold the card in dispenser” set - 1 byte unsigned CHAR
READ_CARD_HOLD = 0x88      # Read “Hold the card in dispenser” set  - no data
WRITE_DELAY = 0x89         # Write “Delay Time” in secs             - 1 byte unsigned CHAR
READ_DELAY = 0x8A          # Read “Delay Time” in secs              - no data
RESET_EEPROM = 0x92        # Reset EEPROM values to default factory values - no data

# eh?
SET_MODE = 0x90      # Set Card Dispenser/Motor Control Mode - 1 byte unsigned CHAR
MOTOR_ACTIVE = 0x91  # Motor Active Control                  - 2 bytes unsigned CHAR
READ_OPERATION = 0x92 # Read Motor Operation Type: Turn Counter/Timer - 2 bytes unsigned CHAR
WRITE_OPERATION = 0x93 # Write Motor Operation Type: Turn Counter/Timer - 2 bytes unsigned CHAR
READ_MOTOR_TURNS = 0x94 # Read Motor Number of Turns Value   - 4 bytes unsigned CHAR
WRITE_MOTOR_TURNS = 0x95 # Write Motor Number of Turns Value - 4 bytes unsigned CHAR
READ_TIMER = 0x96    # Read Motor Timer value                - 4 bytes unsigned CHAR
WRITE_TIMER = 0x97   # Write Motor Timer value               - 4 bytes unsigned CHAR
MOTOR_STATUS = 0x98  # Motor Control Status                  - 2 bytes unsigned CHAR
MOVE_TO_HOME = 0x99  # Move Motor Position to “Home” Position- 2 bytes unsigned CHAR
READ_ADJUST_TIME = 0x9A # Read Home Position Trim Adjustment Time - 4 bytes unsigned CHAR
WRITE_ADJUST_TIME = 0x9B # Write Home Position Trim Adjustment Time - 4 bytes unsigned CHAR
MOTOR_CONTROL_STATUS = 0x9F # 

# Reserved Response Codes
ACK = 0x06  # Accepted/Positive Status
NAK = 0x15  # Rejected/Negative Status
INC = 0xFD  # Incomplete Command Packet
UNR = 0xFE  # Unrecognized Command Packet
CER = 0xFF  # Data Packet Checksum Error

# status values
READY = 0x30         # Ready to dispense the card
BUSY  = 0x31         # The card dispenser is busy dispensing the card
EMPTY = 0x32         # No cards inside the card dispenser stack
STUCK = 0x33         # Card is jammed inside the card dispenser
CARDHOLD = 0x34      # Card is dispensed, but not yet removed
DISABLED = 0x35      # 
CHECK_SENSORS = 0x36 #
LOW_CARD = 0x37      # 

ser = serial.Serial(
	port='/dev/tty.usbserial-0000201A',
	baudrate=19200,
        bytesize=8,
        parity='N',
        stopbits=1,
        xonxoff=0,
        rtscts=0,
        timeout=1
)

ser.open()

def _checksum(packet):
    '''calculate the XOR checksum of a packet in string format'''
    xorsum = 0
    for s in packet:
        xorsum ^= ord(s)
    return xorsum

def _printpacket(packet):
    packetprint = ''
    for s in packet:
        packetprint += hex(ord(s)) + ' '
    print(packetprint)


def receivepacket():
    bytes = []
    endofpacket = False
    while not endofpacket and ser.inWaiting():
        byte = ser.read()
        print 'byte: ' + str(byte)
        if byte != '':
            bytes.append(byte)
        if byte == ETX: endofpacket = True
    # don't forget the checksum...
    if ser.inWaiting():
        bytes.append(ser.read())
    return bytes


def parsecommand(packet):
    '''parse the "command" byte from the response packet to get a "response code"'''
    cmd = ord(packet[2])
    if cmd == ACK: # Accepted/Positive Status
        print 'ACK - Accepted/Positive Status'
    elif cmd == NAK: # Rejected/Negative Status
        print 'NAK - Rejected/Negative Status'
    elif cmd == INC: # Incomplete Command Packet
	print 'INC - Incomplete Command Packet'
    elif cmd == UNR: # Unrecognized Command Packet
        print 'UNR - Unrecognized Command Packet'
    elif cmd == CER: # Data Packet Checksum Error
        print 'CER - Data Packet Checksum Error'
    else:
        raise Exception('Received bad CMD in response from card dispenser')

    print packet


def parsedata(packet):
    '''parse the data section of a packet, it can range from 0 to many bytes'''
    data = []
    datalength = ord(packet[3])
    position = 0
    while position < datalength:
        data.append(packet[position + 3])
    return data


def parseresponse(packet):
    if ord(packet[0]) != STX or ord(packet[-2]) != ETX:
        print 'this is not a packet: ' + str(packet)
        # this is not a packet, it could be the startup string, or a
        # garbled package, or something else
        return
    receivedchecksum = ord(packet[-1])
    print packet[0:-1]
    calculatedchecksum  = _checksum(packet[0:-1])
    print str(receivedchecksum) + ' == ' + str(calculatedchecksum)
    parsecommand(packet)

# <STX><ADD><CMD><LEN><DTA><ETX><CHK>
def sendcommand(command, datalength=0, data=None):
    '''send a packet in the vendapin format'''
    packet = chr(STX) + chr(ADD) + chr(command) + chr(datalength)
    if datalength > 0:
        packet += chr(data)
    packet += chr(ETX)
    sendpacket = packet + chr(_checksum(packet))
    _printpacket(sendpacket)
    ser.write(sendpacket)


#------------------------------------------------------------------------------#
# for testing from the command line:
def main(argv):
    print('GO!')
#    print sendcommand(REQUEST_STATUS)
#    time.sleep(2)
    print sendcommand(DISPENSE)
    waiting = True
    while waiting:
        if ser.inWaiting() > 0:
            waiting = False
    response = receivepacket()
    print 'response: ' + str(response)
    parseresponse(response)
    print('inWaiting: ' + str(ser.inWaiting()))
    ser.close()
    
if __name__ == "__main__":
    main(sys.argv[1:])


