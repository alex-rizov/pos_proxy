import logging.config
import logging
import os
from logging.handlers import TimedRotatingFileHandler

def setup_logging(working_folder, format='%(asctime)s [%(filename)s:%(lineno)s - %(funcName)20s() %(levelname)s] %(message)s', level=logging.INFO):
    logging.basicConfig(format=format, level=level)        

    logger = logging.getLogger() #gets the root logger for the application

    file = os.path.join(working_folder, "log/PosProxy.log")
    os.makedirs(os.path.dirname(file), exist_ok=True)
    
    handler = TimedRotatingFileHandler(file, when = 'midnight', backupCount=30)
    handler.setLevel(logging.DEBUG)

    formatter = logging.Formatter(format)  
    handler.setFormatter(formatter)
    
    logger.addHandler(handler)
       
       