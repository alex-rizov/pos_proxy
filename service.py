import win32serviceutil
import win32service
import win32event
import win32api
import servicemanager
import socket
import time
import logging
import sys
import os
import subprocess 
import random
import asyncio
import pos_proxy.runner as runner
import pos_proxy.logging_setup



def delete_old_bundle_dirs(path_to_current):
        base_dir = os.path.join('C:/', 'ProgramData', 'Midax', 'PosProxy')
        if os.path.exists(base_dir):
                for child_dir in os.listdir(base_dir):
                        full_dir = os.path.join(base_dir, child_dir)
                        if not os.path.isdir(full_dir):
                                continue

                        if os.path.normpath(full_dir) == os.path.normpath(path_to_current):
                                continue
                        try:
                                delete_tree_or_file(full_dir)
                        except:
                                pass

class AppServerSvc (win32serviceutil.ServiceFramework):
    _svc_name_ = "MidaxPosProxy"
    _svc_display_name_ = "Midax POS Proxy"
    _svc_description_ = "Switching proxy for loyalty providers with different card prefixes or other criteria."

    def __init__(self,args):
        win32serviceutil.ServiceFramework.__init__(self,args)       
        socket.setdefaulttimeout(60)
        self.isAlive = True 
        self.loop = None             

    def SvcStop(self):      
        if self.loop is not None:         
            future = asyncio.run_coroutine_threadsafe(runner.stop(), self.loop)

            future.result(timeout = 10) #we wait for max 10 seconds for everything to stop
            
            self.loop.call_soon_threadsafe(self.loop.stop)
            self.isAlive = False

    def SvcDoRun(self):
        self.isAlive = True
        servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
                              servicemanager.PYS_SERVICE_STARTED,
                              (self._svc_name_,''))
        self.main()                         

    def main(self):
        
        if getattr(sys, 'frozen', False):
    # If the application is run as a bundle, the pyInstaller bootloader
    # extends the sys module by a flag frozen=True and sets the app 
    # path into variable _MEIPASS'.
            application_path = sys._MEIPASS
            try:
                delete_old_bundle_dirs(path_to_current = application_path)
            except:
                pass
        else:
            application_path = os.path.dirname(os.path.abspath(__file__))      
     
        pos_proxy.logging_setup.setup_logging(os.path.dirname(win32api.GetModuleFileName(None)))
        logging.getLogger('root').info('Service starting')
        try:
            asyncio.set_event_loop(asyncio.new_event_loop())
            self.loop = asyncio.get_event_loop()                   
            task = asyncio.ensure_future(runner.run(os.path.dirname(win32api.GetModuleFileName(None))))
            self.loop.run_until_complete(task)
            
            task.result()
            #if we're successful so far, initialization is done and we start the loop
            self.loop.run_forever()
        except Exception as e:
            logging.getLogger('root').exception(e)    

        logging.getLogger('root').info('Service shutting down')        
        
        
            


if __name__ == '__main__':
    argv = sys.argv
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(AppServerSvc)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        if 'install' in argv and '--startup' not in argv:
            index_of_install = argv.index('install')
            argv.insert(index_of_install, 'auto')
            argv.insert(index_of_install, '--startup')     
        win32serviceutil.HandleCommandLine(AppServerSvc, argv=argv)
