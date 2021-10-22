import asyncio
import struct
import binascii
import logging
import xml.etree.ElementTree as ET
from .client import read_all_message_bytes, MessageHandlingType
from .handler import PosHandler



class PassportHandler(PosHandler):
    """
    Implementation of a PosHandler for Passport Loyalty protocol.
    """
    def __init__(self):
        self.header_bytes_length = 28
        self._logger = logging.getLogger(self.__class__.__name__)


    def process_header(self, input : bytes) -> (int, int, bytes):
        """
        Reads the header meta-data, verifies formatting and CRC checksum and
        returns the contained info.
        Input: bytes - the message to process
        Returns:
            xml_length - the length of the XML message following the header
            crc_data - CRC of the following message
            bytes - the raw processed header 
        """
        signature =  input[0:10].decode()        
        assert signature == "POSLOYALTY", "First 10 bytes are not POSLOYALTY"
        assert input[10] == 0, "11th byte is not 0"
        assert input[11] == 0, "12th byte is not 0"

        #read bytes 12 to 15 in netowrk byte order as int
        message_type = struct.unpack("<I", input[12:16])[0]        
        assert message_type == 1 or message_type == 2, "Invalid message type"

        xml_length = struct.unpack("<I", input[16:20])[0]

        crc_data = struct.unpack("<I", input[20:24])[0]
        crc_header = struct.unpack("<I", input[24:28])[0]
        
        assert crc_header == (binascii.crc32(input[0:24]) & 0xffffffff), "Invalid header CRC"

        return xml_length, crc_data, input[0:28]

    def verify_message(self, message: bytes):
        """
        Verifies that this is a good formatted Passport message and all CRCs match.
        Input: bytes - the message to verify        
        """
        _, crc_data, _ = self.process_header(message)

        if crc_data > 0:                    
            assert crc_data == (binascii.crc32(self.get_xml(message)) & 0xffffffff), "Invalid message XML CRC"

    async def read_and_process_header(self, reader: asyncio.StreamReader) -> (int, bytes):
        """
        Waits until all header bytes are received and processes them.
        Input: reader - the asyncio stream reader to use for reading       
        Output:
            length - the lenght of the XML portion following the header
            header_bytes - the raw header data
        """
        header_bytes = await read_all_message_bytes(reader, self.header_bytes_length)        
        xml_length, _, header_bytes = self.process_header(header_bytes)
        return xml_length, header_bytes
    
    def get_xml(self, message:bytes) -> bytes:
        """
        Returns the XML portion of the message.
        """
        return message[28:]

    def is_binary_echo(self, message:bytes) -> bool:
        """
        Checks if this is a binary echo message.
        """
        message_type = struct.unpack("<I", message[12:16])[0]    
        if message_type == 2:
            return True

        return False

    def get_message_handling_type_and_identifier(self, message: bytes) -> (MessageHandlingType, str, str):
        """
        Returns the basic routing info for a message.
        Input: message - the message as bytes
        Returns:
            MessageHandlingType - the base handling type of the message
            routing_id - card if card routing, session if session routing - dispatcher should route on that
            session_id - the session id for maintaining sessions, if available
        """        
        self.verify_message(message)

        if self.is_binary_echo(message):
            return MessageHandlingType.MULTICAST_WITH_RESPONSE, None, None

        xml_bytes = self.get_xml(message)
        root = ET.fromstring(xml_bytes.decode())

        for _ in root.iter('GetLoyaltyOnlineStatusRequest'):
            return MessageHandlingType.MULTICAST_WITH_RESPONSE, None, None

        for _ in root.iter('GetLoyaltyOnlineStatusResponse'):
            return MessageHandlingType.MULTICAST_WITH_RESPONSE, None, None

        for _ in root.iter('BeginCustomerRequest'):
            return MessageHandlingType.MULTICAST_NO_RESPONSE, None, None
        
        for _ in root.iter('EndCustomerRequest'):
            return MessageHandlingType.MULTICAST_NO_RESPONSE, None, None
        
        #If we have card #, route based on card #, but still record session ID if available
        for node in root.iter('LoyaltyID'):
            if node.text:
                session_id = None
                for ses_node in root.iter('LoyaltySequenceID'):
                    if ses_node.text:
                        session_id = ses_node.text
                        break
                return MessageHandlingType.CARD_BASED_UNICAST, node.text, session_id
        
        #If no card #, route based on Session
        for node in root.iter('LoyaltySequenceID'):
            if node.text:
                return MessageHandlingType.SESSION_BASED_UNICAST, node.text, node.text        

        #Nothing to base routing on, default route
        return MessageHandlingType.DEFAULT_UNICAST, None, None

    def get_sequence_id(self, message: bytes) -> (str):
            """
            Returns the unique message sequence ID.
            Input: message - the complete message to get the sequnce ID from
            Returns:
                sequence id - the sequence if from the message, PASSPORT_ECHO if binary echo
            """        
            self.verify_message(message)

            if self.is_binary_echo(message):
                return 'PASSPORT_ECHO'

            xml_bytes = self.get_xml(message)
            root = ET.fromstring(xml_bytes.decode())

            for node in root.iter('POSSequenceID'):
                return node.text
            
    def verify_sequence_id(self, request: bytes, response: bytes) -> (bool):
        return (self.get_sequence_id(request) == self.get_sequence_id(response))

#Should return the response message (bytes, and whether the message is echo or not)
    async def wait_and_handle_response_message(self, reader: asyncio.StreamReader, request: bytes) -> (bytes, MessageHandlingType, str):
        """
        Waits for a fully received response using the provided StreamReader and returns the response and its meta-data.
        Input: 
            reader - the StreamReader to use
            request - the request message that has been sent already that we are waitig a response for - it is needed in order to internally recognize its response policy.
        Returns: 
            response - the awaited response
            message_type - the message type of the response
            session_id - the session number, if available, for the caller to track sessions

        Raises:
            SocketClientError - if sockets get closed before receiving a full message.
        """

        message_type, _, _ = self.get_message_handling_type_and_identifier(request)
        if message_type == MessageHandlingType.MULTICAST_NO_RESPONSE:
            return None, MessageHandlingType.MULTICAST_NO_RESPONSE, None

        xml_length, header_bytes = await self.read_and_process_header(reader)

        xml_bytes = await read_all_message_bytes(reader, xml_length)

        response = header_bytes + xml_bytes
        message_type, _, session_id = self.get_message_handling_type_and_identifier(response)

        assert self.verify_sequence_id(request, response), "Response SequenceID doesn't match request"

        return response, message_type, session_id

    async def wait_and_handle_request_message(self, reader: asyncio.StreamReader) -> (bytes, MessageHandlingType, str, str):
        """
        Waits for a fully received request using the provided StreamReader and returns the received whole message and its meta-data.
        Input: 
            reader - the StreamReader to use            
        Returns: 
            message - the awaited complete message
            message_type - the message type
            routing_id - the ID around which to base roting one, dependant on type
            session_id - the session number, if available, for the caller to track sessions
        
        Raises:
            SocketClientError - if sockets get closed before receiving a full message.
        """
        xml_length, header_bytes = await self.read_and_process_header(reader)

        xml_bytes = await read_all_message_bytes(reader, xml_length)

        message = header_bytes + xml_bytes
        message_type, routing_id, session_id = self.get_message_handling_type_and_identifier(message)
        return message, message_type, routing_id, session_id