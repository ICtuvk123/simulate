import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'code'))
from practice_transport import PracticeTransport
from q3client import ProtocolError


class PracticeTransportTests(unittest.TestCase):
    def test_no_permission_or_remote_origin_cannot_open_connection(self):
        calls=[]
        factory=lambda *a,**k:calls.append((a,k))
        with self.assertRaises(ProtocolError):PracticeTransport('http://127.0.0.1:2026','',factory)
        for url in ('http://192.0.2.1:2026','http://localhost:2026','http://127.0.0.1:2026/hidden','http://127.0.0.1:2026?mode=formal'):
            with self.assertRaises(ProtocolError):PracticeTransport(url,'I_HAVE_SELECTED_PRACTICE',factory)
        self.assertEqual(calls,[])
    def test_only_documented_endpoint_and_unmodified_body(self):
        calls=[]
        class Response:
            status=200
            def read(self):return b'{"accepted":false,"virtual_time_s":0,"real_timestamp_ms":0}'
        class Connection:
            def __init__(self,*a,**k):calls.append(('connect',a,k))
            def request(self,*a,**k):calls.append(('request',a,k))
            def getresponse(self):return Response()
            def close(self):calls.append(('close',))
        t=PracticeTransport('http://127.0.0.1:2026','I_HAVE_SELECTED_PRACTICE',Connection)
        with self.assertRaises(ProtocolError):t('/scene',b'{}',5)
        self.assertEqual(calls,[])
        body=b'{"request_id":"unchanged"}'
        status,result=t('/measure',body,4)
        self.assertEqual(status,200);self.assertEqual(calls[1][1],('POST','/measure'))
        self.assertEqual(calls[1][2]['body'],body)
        self.assertEqual(calls[-1],('close',))


if __name__=='__main__':unittest.main()
