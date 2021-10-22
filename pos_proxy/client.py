import asyncio
import time
import logging
import binascii
from uuid import uuid4
from enum import Enum


class TimeoutNotExpiredError(Exception):
    pass

class SocketClientError(Exception):
    pass



class MessageHandlingType(Enum):
    CARD_BASED_UNICAST = 1
    SESSION_BASED_UNICAST = 2
    DEFAULT_UNICAST = 3
    MULTICAST_WITH_RESPONSE = 4
    MULTICAST_NO_RESPONSE = 5


async def read_all_message_bytes(reader: asyncio.StreamReader, total_bytes: int) -> bytearray:
    """
    Read exactly X bytes from reader and returns when the specified number of bytes has been received
    Input:
        reader - the reader to use
        total_bytes - the number of bytes to read
    Returns:
        bytes - the bytes received
    Raises:
        SocketClientError - socket was closed before specified number of bytes could be read
    """
    bytes_read = 0
    whole_message = bytearray()
    while True:
        new_bytes = await reader.read(total_bytes - bytes_read)
        if not new_bytes:
            raise SocketClientError("Socket closed.")
        bytes_read += len(new_bytes)
        whole_message += new_bytes
        if bytes_read == total_bytes:
            return whole_message


class SocketClient(object):
    """ 
    Provides an asynchronous interface that represents a client connection to 1 remote host.
    """
    def __init__(self, protocol_handler, host, port, retry_timeout = 150, connect_timeout = 10, response_timeout = 10, masks = []):
        self.host = host
        self.port = port
        self.reader = None
        self.writer = None
        self.protocol_handler = protocol_handler
        self._connected = False
        self.host = host
        self.port = port
        self.retry_timeout = retry_timeout
        self.connect_timeout = connect_timeout
        self.response_timeout = response_timeout
        self.last_disconnect_retry = None
        self.masks = masks
        self.uuid = uuid4()
        self.__lock = asyncio.Lock()
        self._logger = logging.getLogger(self.__class__.__name__ + '.' +str(self.uuid))
        self._logger.info('Client initialized to {}:{}'.format(str(self.host), str(self.port)))

    @property
    def connected(self):
        return self._connected

    @connected.setter
    def connected(self, connected):
        if connected == False:
            self.writer = None
            self.reader = None

            if self._connected == True:
                self.last_disconnect_retry = time.time()

        self._connected = connected

    async def connect(self):        
        if self.connected == True:
            return
        
        if self.last_disconnect_retry is not None and time.time() < (self.last_disconnect_retry + self.retry_timeout):
            raise TimeoutNotExpiredError

        self.last_disconnect_retry = time.time()
        future_connection = asyncio.open_connection(self.host, self.port)
        try:
            self.reader, self.writer = await asyncio.wait_for(future_connection, self.connect_timeout)       
            self.connected = True
            self._logger.info('Client connected to {}:{}'.format(str(self.host), str(self.port)))
            return
        except:
            self.connected = False
            self._logger.error('Client could not establish connection to {}:{}'.format(str(self.host), str(self.port)))
            raise

    async def disconnect(self):
        if self.connected == False:
            return

        self.writer.close()  
        await self.writer.wait_closed()
        self._logger.info('Client disconnected from {}:{}'.format(str(self.host), str(self.port)))
        self.connected = False             
        
            
    async def send(self, message : bytes):
        await self.connect()

        await self.writer.drain()
        self.writer.write(message)        
        self._logger.info('Forwarded message to remote host')
        self._logger.debug('Sent: {}'.format(binascii.hexlify(message)))
        
    async def send_and_wait_response(self, message : bytes):
        await self.send(message)        
        response, message_type, session_id = await self.protocol_handler.wait_and_handle_response_message(reader = self.reader, request = message)
        self._logger.info('Received response from remote host, Message type: {}, Session Id:{}'.format(message_type, session_id))
        if response is not None:
            self._logger.debug('Received: {}'.format(binascii.hexlify(response)))
        return response, message_type, session_id
    
    async def send_and_wait_response_with_timeout(self, message : bytes):
        async with self.__lock:
            try:
                return await asyncio.wait_for(self.send_and_wait_response(message), self.response_timeout)
            except:
                await self.disconnect()
                raise