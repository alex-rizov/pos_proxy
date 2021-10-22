#!/usr/bin/env python3

import asyncio
import logging
logging.basicConfig(level=logging.DEBUG)


def _DEFAULT_REPLY_CB(message):
	return message

class MockTCPServer:

	"""Implements a simple mock TCP server that responds to received
	messages. Closes the client socket after one message.
	By default, the server responds with a copy of the received message.
	Reply message can be customized using `reply_cb` callback function.
	This has to be a pure function that takes one input (input message)
	and outputs a reply to be sent to the client (preferably in bytes). 
	"""

	def __init__(self, port=18898, reply_cb=_DEFAULT_REPLY_CB, timeout = False):
		self._port = port
		self._reply_cb = reply_cb		
		self.timeout = timeout
		self.message_received = False
		self.message_received_event = asyncio.Event()
		self._logger = logging.getLogger(self.__class__.__name__)	
		self.writers = []
		

	async def listen(self):
		self._server = await asyncio.start_server(
			self.__on_connection, host='127.0.0.1', port=self._port)
		
		self._logger.info('Listening on port %s' % self._port)		
		return self

	async def __on_connection(self, reader, writer):
		self._logger.info(
			'Received connection from someone')
		
		self.writers.append(writer)
		while True:
			message = await reader.read(4096)
			if not message:
				break
			self._logger.info(
				'Received message from "%s:%s"' % writer.get_extra_info('peername'))
			self.message_received = True
			self.message_received_event.set()
			
			if (self.timeout is not True):				
				# Compute a reply message from provided `reply_cb` function
				reply = self._reply_cb(message)				
				self._logger.info('Sending response... {}'.format(reply))
				writer.write(
					reply if type(reply) == bytes else reply.encode('ascii'))
				await writer.drain()
						
		

	async def close(self):		
		for writer in self.writers:
			if writer.is_closing() is False:
				writer.close()
				await writer.wait_closed()
		self._server.close()
		await self._server.wait_closed()

	@property
	def port(self):
		return self._port

if __name__ == '__main__':
	"""Runs standalone as well."""
	try:
		loop = asyncio.get_event_loop()
		asyncio.ensure_future(MockTCPServer(), loop=loop)
		loop.run_forever()
	except KeyboardInterrupt:
		print('\nBye!')