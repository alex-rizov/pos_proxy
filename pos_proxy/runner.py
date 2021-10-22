from .logging_setup import setup_logging
from .dispatcher import DispatcherServer
from .sessions import SessionHandler
import logging
import configparser
import os

servers = []
session_handler = None
logger = logging.getLogger( __name__ )

def get_all_init_files(working_folder):
    for filename in os.listdir(working_folder):
        if filename.casefold().endswith('.proxy') is False:
            continue

        if os.path.isfile(os.path.join(working_folder, filename)) is False:
            continue

        yield os.path.join(working_folder, filename)


async def run(working_folder):    
    logger = logging.getLogger( __name__ )
    logger.info("Starting up")    

    with open(os.path.join(working_folder, 'POSPROXY.ver'), 'a'):
        pass

    init_files = [x for x in get_all_init_files(working_folder)]
    
    if len(init_files) == 0:
        logger.error("No .proxy files")
        raise ValueError("No .proxy files. Cannot start")

    session_handler = SessionHandler(working_folder).open()
    
    for filename in init_files:
        try:
            print(filename)
            config = configparser.ConfigParser()
            config.read(filename) 
            server = DispatcherServer(config, session_handler)         
            await server.listen()
            servers.append(server)
        except Exception as e:
            logger.error(e)       
    

async def stop():
    logger.info("Shutting down")
    for server in servers:
        await server.close()

    if session_handler is not None:
        session_handler.close()