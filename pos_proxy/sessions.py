import sqlite3
import os
import asyncio

class SessionHandler():
    def __init__(self, folder_path):
        self.__db_file_name = os.path.join(folder_path, 'sessions', 'sessions.db')             
        self.__conn = None
        self.__cleanup_task = None

    def open(self):
        os.makedirs(os.path.dirname(self.__db_file_name), exist_ok=True)
        self.__conn = sqlite3.connect(self.__db_file_name)
        self.__conn.execute("CREATE TABLE IF NOT EXISTS SessionUsers(session_id TEXT PRIMARY KEY, user_id TEXT, Timestamp DATETIME DEFAULT CURRENT_TIMESTAMP);")
        self.__conn.commit()
        self.__cleanup_task = asyncio.create_task(self.eod())
        return self

    def close(self):
        self.__cleanup_task.cancel()
        self.__conn.close() 

    def __enter__(self):        
        return self.open()        

    def __exit__(self, *exc):         
        self.close()

    def write_user(self, session, user):
        self.__conn.execute("REPLACE INTO SessionUsers(session_id, user_id, Timestamp) VALUES(?, ?, CURRENT_TIMESTAMP);", (session, user,))
        self.__conn.commit()

    def get_user_for_session(self, session):
        self.__conn.execute("SELECT user_id FROM SessionUsers WHERE session_id = ?;", (session,))
        return self.__conn.fetchone()

    async def eod(self):
        while True:
            self.__conn.execute("DELETE FROM SessionUsers WHERE Timestamp < DATE('now', '-2 days');")
            self.__conn.commit()
            await asyncio.sleep(60 * 60 * 24) #repeat every day