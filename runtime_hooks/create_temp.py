import os
import sys

if getattr(sys, 'frozen', False):
    # If the application is run as a bundle, the pyInstaller bootloader
    # extends the sys module by a flag frozen=True and sets the app 
    # path into variable _MEIPASS'.    
            
    if not os.path.isdir(os.path.join('c:/','ProgramData', 'Midax')):
        os.mkdir(os.path.join('c:/','ProgramData', 'Midax'))

    base_dir = os.path.join('c:/','ProgramData', 'Midax', 'PosProxy')
    if not os.path.isdir(base_dir):
        os.mkdir(base_dir)

    