
import abc
import asyncio 
from .client import MessageHandlingType

class PosHandler(abc.ABC):
    """
    ABC class (abstract class) defining the universal interface which the Dispatcher can use to process individual POS protocols.
    """
    @abc.abstractmethod
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
        pass

    @abc.abstractmethod
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
        pass