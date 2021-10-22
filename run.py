# the run class
import signal
signal.signal(signal.SIGINT, signal.SIG_DFL)

import pos_proxy.runner as runner
import os.path
import asyncio
import os



def main():
        loop = asyncio.get_event_loop()          
        #loop.run_until_complete(runner.run(os.getcwd()))
        asyncio.ensure_future(runner.run(os.getcwd()))        
        loop.run_forever()


if __name__ == "__main__":
        main()