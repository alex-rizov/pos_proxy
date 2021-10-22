import asyncio
import logging
import binascii
import fnmatch
from uuid import uuid4
from .handler import PosHandler
from .passport_handler import PassportHandler
from .client import MessageHandlingType, SocketClient


class NoClientConnectedError(Exception):
    pass


class DispatchedMessage:
	def __init__(self, request):
		self.request = request
		self.responded = False
		self.user_id = None


class Dispatcher:
	"""
	Handles messaged coming from one POS source (represented by a reader/writer pair).
	Needs also pre-initilized clients and a handler instance to handle POS messages.
	"""
	def __init__(self, reader: asyncio.StreamWriter, writer: asyncio.StreamWriter, clients, handler, session_handler):
		self.reader  = reader
		self.writer = writer
		self.clients = clients
		self.handler = handler
		self.__session_handler = session_handler
		self.uuid = uuid4()
		self._logger = logging.getLogger(self.__class__.__name__ + '.' + str(self.uuid))

	async def __aenter__(self): 
		return self
  
	async def __aexit__(self,type, value, traceback):
		self._logger.info('Closing all peer sockets.')
		for client in self.clients:
			await client.disconnect()
		
		if self.writer is not None:
			self.writer.close()
			await self.writer.wait_closed()

	def get_valid_clients(self, dispatched_message: DispatchedMessage, message_type: MessageHandlingType, routing_id: str, session_id: str):
		if message_type == MessageHandlingType.MULTICAST_NO_RESPONSE or message_type == MessageHandlingType.MULTICAST_WITH_RESPONSE:
			return self.clients
		
		if message_type == MessageHandlingType.SESSION_BASED_UNICAST:
			try:
				routing_id = self.__session_handler.get_user_for_session(routing_id)
				assert routing_id is not None
			except:
				self._logger.error('Cannot find user ID for session.')
				message_type == MessageHandlingType.DEFAULT_UNICAST

		if message_type == MessageHandlingType.CARD_BASED_UNICAST:
			dispatched_message.user_id = routing_id

		if message_type == MessageHandlingType.CARD_BASED_UNICAST or message_type == MessageHandlingType.SESSION_BASED_UNICAST:
			def filter_masks(v):
				return len(list(filter(lambda x: fnmatch.fnmatch(routing_id, x + '*'), v.masks)))
			client_candidates = list(filter(filter_masks, self.clients))
			if len(client_candidates) > 0:
				return client_candidates[:1] #return first match
			
		return self.clients[:1]#in all other cases, forward to first (default) client

	async def dispatch_to_client_and_respond_if_first_answer(self, message:DispatchedMessage, client: SocketClient):
		self._logger.debug('Sending message to remote peer')
		response, _, session_id = await client.send_and_wait_response_with_timeout(message.request)
		if message.responded is True:
			return

		message.responded = True		
		if response is not None and self.writer is not None:
			await self.writer.drain()
			self.writer.write(response)        
			self._logger.info('Forwarded response to "%s:%s"' % self.writer.get_extra_info('peername'))
			self._logger.debug('Sent: {}'.format(binascii.hexlify(response)))

		if session_id is not None and self.__session_handler is not None and message.user_id is not None:
			self.__session_handler.write_user(session_id, message.user_id)

		

	async def dispatch_and_respond(self, message: bytes, message_type: MessageHandlingType, routing_id: str, session_id: str):		
		dispatched_message = DispatchedMessage(message)
		valid_clients = self.get_valid_clients(dispatched_message, message_type, routing_id, session_id)
		success = False
		for f in asyncio.as_completed([self.dispatch_to_client_and_respond_if_first_answer(dispatched_message, client) for client in valid_clients], timeout = 30):
			try:
				await f	
				success = True #we just need one success (lack of exception) to consider the message successfully processed
			except Exception:				
				self._logger.exception("Exception in a dispatch task.")

		if success is False:
			self._logger.error("Could not dispatch to any good client. Closing POS connection.")			
			self.writer.close()	#this will create a socket event which in turn raises an exception in the read triggering a dispatcher close - somewhat fiddly but efficient
	

	async def loop_await_dispatch_and_respond(self):
		tasks = []		
		finished = False
		while True:		
			try:						
				message, message_type, routing_id, session_id = await self.handler.wait_and_handle_request_message(self.reader)			
				self._logger.info('Received message from "%s:%s"' % self.writer.get_extra_info('peername'))
			
				dispatch_task = asyncio.create_task(self.dispatch_and_respond(message, message_type, routing_id, session_id))
				tasks.append(dispatch_task)								
			except Exception:
				self._logger.exception("POS socket exception.")				
				finished = True
			finally:
				#we go over completed tasks and we break out if an exeption occurred
				completed_tasks = [task for task in tasks if task.done() is True]
				tasks = [task for task in tasks if task.done() is not True]
				try:
					for task in completed_tasks:
						task.result() #this will raise an exception if the async task also raised any exception so we will break out
				except Exception:				
					self._logger.exception("Exception in a dispatch and respond task.") #should never really happen, dispatch and respond does not raise
					finished = True

			if finished is True:
				break

		for task in tasks:
			task.cancel()
				
class DispatcherServer:	
	"""
	Represents a server, waiting on a specified port. Initializes Dispatchers and Clients, based on input configuration.
	Input conifguration:

	[HOST] #represents the listener
	Port = 19999 #the port to listen on
	PosType = PASSPORT #the type of Register. Supported are: PASSPORT

	[CLIENT-1] #represents one client to forward messages to - this first one in the list is also the default client when none other match
	Remote = X #the host name of the remote
	Port = X the port # to connect to
	CardMasks = 425001, 425002

	[CLIENT-2] #second client to forward messages to
	.... - same as CLIENT-1

	[....] #Client 3 and further
	"""
	def __init__(self, config, session_handler):				
		self._port = config['HOST'].getint('Port')
		self.__session_handler = session_handler
		handler_string = config['HOST'].get('PosType', 'PASSPORT')

		if handler_string == 'PASSPORT':			
			self.handler = PassportHandler()
		else:
			raise ValueError("Unknown POS Type {}".format(handler_string))

		self.config = config
		self.uuid = uuid4()
		self._logger = logging.getLogger(self.__class__.__name__ + '.'  + str(self.uuid))
		self.writers = []	
		self._server = None
		
	async def __aenter__(self): 
		await self.listen()
		return self
  
	async def __aexit__(self, type, value, traceback):
		await self.close()

	async def listen(self):
		self._server = await asyncio.start_server(
			self.__on_connection, host='127.0.0.1', port=self._port)
		
		self._logger.info('Listening on port %s' % self._port)
		return self


	async def __on_connection(self, reader, writer):
		self._logger.info('Received connection from POS "%s:%s"' % writer.get_extra_info('peername'))
		self.writers.append(writer)
		
		try:
			clients_config = [self.config[x] for x in self.config.sections() if x not in ['HOST', 'DEFAULT']]
			
			clients = [SocketClient(protocol_handler = self.handler, host = cli_cfg['Remote'], port = cli_cfg.getint('Port'), masks = [x.strip() for x in cli_cfg.get('CardMasks', '').split(',')]) for cli_cfg in clients_config]		
			
			async with Dispatcher(reader, writer, clients, self.handler, session_handler = self.__session_handler) as dispatcher:
				await dispatcher.loop_await_dispatch_and_respond()
			
		except Exception:			
			self._logger.exception("Exception processing POS message.")	 #nobody higher listens for exceptions on this task	
		finally:			
			self.writers.remove(writer)	
			if writer.is_closing() is False:
				self._logger.info('Closing POS connection.')
				writer.close()
				await writer.wait_closed()

		
    
	async def close(self):		
		for writer in self.writers:
			if writer.is_closing() is False:
				writer.close()
				await writer.wait_closed()
		
		if self._server is not None:
			self._server.close()
			await self._server.wait_closed()