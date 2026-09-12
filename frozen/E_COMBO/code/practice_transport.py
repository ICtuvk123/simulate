"""Manual practice adapter: exactly four documented loopback HTTP endpoints.

Imported only by official_practice.py, never by local experiments. There is no
official mode query in the published API: the operator must select PRACTICE in
the official UI before explicitly starting this separate entry point.
"""
import http.client,ipaddress
from urllib.parse import urlsplit
from q3client import ProtocolError


class PracticeTransport:
    def __init__(self,base_url,confirmation,connection_factory=http.client.HTTPConnection):
        if confirmation!='I_HAVE_SELECTED_PRACTICE':
            raise ProtocolError('Explicit manual practice selection is required')
        u=urlsplit(base_url)
        try:local=ipaddress.ip_address(u.hostname or '').is_loopback
        except ValueError:local=False
        if not(local and u.scheme=='http' and not u.username and not u.password and u.path in ('','/') and not u.query and not u.fragment):
            raise ProtocolError('Only a numeric loopback HTTP origin is allowed')
        self.host=u.hostname;self.port=u.port or 2026;self.factory=connection_factory

    def __call__(self,path,body,timeout):
        if path not in ('/enter','/measure','/clear','/exit'):
            raise ProtocolError('Undocumented endpoint forbidden')
        connection=self.factory(self.host,self.port,timeout=timeout)
        try:
            connection.request('POST',path,body=body,headers={'Content-Type':'application/json; charset=utf-8','Content-Encoding':'identity'})
            response=connection.getresponse()
            # The client validates both HTTP and business acceptance and retains
            # request_id/body across all uncertain retries.
            return response.status,response.read().decode('utf-8')
        finally:connection.close()
