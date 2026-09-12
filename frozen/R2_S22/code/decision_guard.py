"""Block unapproved data channels while a local decision controller is active."""
import sys


class DecisionGuard:
    def __init__(self):
        self.active=False
        sys.addaudithook(self.check)

    def check(self,event,args):
        if not self.active:return
        if event in ('open','os.listdir','os.scandir','socket.connect','socket.getaddrinfo','subprocess.Popen'):
            raise RuntimeError('Decision data-channel violation: '+event)
        if event=='import' and args[0] in ('q4engine','engine'):
            raise RuntimeError('Decision engine import forbidden')

    def __enter__(self):self.active=True;return self
    def __exit__(self,*exc):self.active=False
