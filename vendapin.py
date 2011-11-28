#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# module to support the Vendapin serial protocol
# http://www.vendapin.com/Adobe%20files/CTD202-203_API.pdf
#

import sys
import serial
import time


class NakException(Exception):
    '''exception for when the device replies with NAK, not succesful'''
    def __init__(self, message, code):
        Exception.__init__(self, message)
        self.code = code

class Vendapin():
    '''control a Vendapin card dispenser via USB-serial'''

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
    RESET = 0x86               # Reset the card dispenser settings - no data or 1 byte unsigned CHAR
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
    READY = '0'         # Ready to dispense the card
    BUSY  = '1'         # The card dispenser is busy dispensing the card
    EMPTY = '2'         # No cards inside the card dispenser stack
    STUCK = '3'         # Card is jammed inside the card dispenser
    CARD_HOLD = '4'     # Card is dispensed, but not yet removed
    DISABLED = '5'
    CHECK_SENSORS = '6'
    LOW_CARD_DETECTED = '7'

    def __init__(self, port='/dev/ttyUSB0'):
        self.serial = serial.Serial(port=port,
                                    baudrate=19200,
                                    bytesize=8,
                                    parity='N',
                                    stopbits=1,
                                    xonxoff=0,
                                    rtscts=0,
                                    timeout=1)

    def open(self):
        return self.serial.open()

    def close(self):
        return self.serial.close()

    def flush(self):
        while self.serial.inWaiting():
            print('(flushed: ' + str(self.receivepacket()) + ')')
        self.serial.flush()
        self.serial.flushInput()
        self.serial.flushOutput()

    def inWaiting(self):
        return self.serial.inWaiting()

    def _checksum(self, packet):
        '''calculate the XOR checksum of a packet in string format'''
        xorsum = 0
        for s in packet:
            xorsum ^= ord(s)
        return xorsum

    def _printpacket(self, packet):
        packetprint = ''
        for s in packet:
            packetprint += hex(ord(s)) + ' '
        print(packetprint)


    def receivepacket(self):
        bytes = []
        endofpacket = False
        while not endofpacket and self.serial.inWaiting():
            byte = self.serial.read()
            if byte != '':
                bytes.append(byte)
            if byte == Vendapin.ETX:
                # got End of Packet, grab checksum and bail
                bytes.append(self.serial.read())
                endofpacket = True
            if byte == '\r': # 'VENDAPIN\r' boot message
                endofpacket = True
        return bytes


    def _matchchecksum(self, packet):
        receivedchecksum = ord(packet[-1])
        calculatedchecksum  = self._checksum(packet[0:-1])
        # TODO perhaps this should throw an Exception when the checksums don't match?
        if receivedchecksum != calculatedchecksum:
            print 'CHECKSUM ERROR' + str(receivedchecksum) + ' != ' + str(calculatedchecksum)
            raise Exception('Checksum failed: ' + str(packet))


    def _validatepacket(self, packet):
        if len(packet) < 7 \
                or ord(packet[0]) != Vendapin.STX \
                or ord(packet[-2]) != Vendapin.ETX:
            raise Exception('this is not a packet: ' + str(packet))
            # this is not a packet, it could be the startup string, or a
            # garbled package, or something else
        self._matchchecksum(packet)


    def was_packet_accepted(self, packet):
        '''parse the "command" byte from the response packet to get a "response code"'''
        self._validatepacket(packet)
        cmd = ord(packet[2])
        if cmd == Vendapin.ACK: # Accepted/Positive Status
            return True
        elif cmd == Vendapin.NAK: # Rejected/Negative Status
            print('NAK - Rejected/Negative Status')
            return False
        elif cmd == Vendapin.INC: # Incomplete Command Packet
            raise Exception('INC - Incomplete Command Packet')
        elif cmd == Vendapin.UNR: # Unrecognized Command Packet
            raise Exception('UNR - Unrecognized Command Packet')
        elif cmd == Vendapin.CER: # Data Packet Checksum Error
            raise Exception('CER - Data Packet Checksum Error')
        else:
            raise Exception('Received bad CMD in response from card dispenser')


    def parsedata(self, packet):
        '''parse the data section of a packet, it can range from 0 to many bytes'''
        data = []
        datalength = ord(packet[3])
        position = 4
        while position < datalength + 4:
            data.append(packet[position])
            position += 1
        return data


    def parsestatus(self, data):
        code = ord(data[0])
        if code == Vendapin.READY:
            print(' response: ready')
        elif code == Vendapin.BUSY:
            raise NakException('NAK response: busy', Vendapin.BUSY)
        elif code == Vendapin.EMPTY:
            raise NakException('NAK response: empty', Vendapin.EMPTY)
        elif code == Vendapin.STUCK:
            raise NakException('NAK response: stuck', Vendapin.BUSY)
        elif code == Vendapin.CARD_HOLD:
            raise NakException('NAK response: card hold', Vendapin.CARD_HOLD)
        elif code == Vendapin.DISABLED:
            raise NakException('NAK response: disabled', Vendapin.DISABLED)
        elif code == Vendapin.CHECK_SENSORS:
            raise NakException('NAK response: check sensors', Vendapin.CHECK_SENSORS)
        elif code == Vendapin.LOW_CARD_DETECTED:
            raise NakException('NAK response: low card detected', Vendapin.LOW_CARD_DETECTED)
        else:
            raise Exception('Bad response code: ' + str(code))


    # <STX><ADD><CMD><LEN><DTA><ETX><CHK>
    def sendcommand(self, command, datalength=0, data=None):
        '''send a packet in the vendapin format'''
        packet = chr(Vendapin.STX) + chr(Vendapin.ADD) + chr(command) + chr(datalength)
        if datalength > 0:
            packet += chr(data)
        packet += chr(Vendapin.ETX)
        sendpacket = packet + chr(self._checksum(packet))
        self._printpacket(sendpacket)
        self.serial.write(sendpacket)


    def request_status(self):
        '''request the status of the card dispenser and return the status code'''
        self.sendcommand(Vendapin.REQUEST_STATUS)
        # wait for the reply
        time.sleep(1)
        response = self.receivepacket()
        if self.was_packet_accepted(response):
            return Vendapin.READY
        else:
            return self.parsedata(response)[0]


    def dispense(self):
        '''dispense a card if ready, otherwise throw an Exception'''
        self.sendcommand(Vendapin.DISPENSE)
        # wait for the reply
        time.sleep(1)
        # parse the reply
        response = self.receivepacket()
        print('Vendapin.dispense(): ' + str(response))
        if not self.was_packet_accepted(response):
            raise Exception('DISPENSE packet not accepted: ' + str(response))
        return self.parsedata(response)[0]


    def reset(self, hard=False):
        '''reset the card dispense, either soft or hard based on boolean 2nd arg'''
        if hard:
            self.sendcommand(Vendapin.RESET, 1, 0x01)
            time.sleep(2)
        else:
            self.sendcommand(Vendapin.RESET)
            time.sleep(2)
            # parse the reply
            response = self.receivepacket()
            print('Vendapin.reset(soft): ' + str(response))
            # this seems to do nothing and fail a lot, so ignore it:
            #if not self.was_packet_accepted(response):
            #    raise Exception('reset reponse not received')


#------------------------------------------------------------------------------#
# for testing from the command line:
# call like ./vendapin.py /dev/ttyUSB0 <# to dispense>
def main(argv):
    # first clear out anything in the receive buffer
    v = Vendapin(port=argv[0])
    v.open()
    time.sleep(1)
    v.reset()
    time.sleep(1)
    v.flush()
    if len(argv) > 1:
        todispense = int(argv[1])
    else:
        todispense = 1
    print('Dispensing ' + str(todispense) + ' cards')
    for x in range(0,todispense):
#        status = None
#        while status != Vendapin.READY:
#            status = v.request_status()
#            print 'NOT READY: ' + status
        v.dispense()
        v.dispense()
        time.sleep(3)
    print('inWaiting: ' + str(v.inWaiting()))
    v.close()
    
if __name__ == "__main__":
    main(sys.argv[1:])


