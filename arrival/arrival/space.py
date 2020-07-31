import requests
import sys
from urllib.parse import urljoin
from .conscodec import ConsCodec


API_HOST = 'https://api.pegovka.space/'


class SpaceTransport:
    def __init__(self, host, api_key=None):
        self.host = host
        self.api_key = api_key
        self.req = requests.Session()

    def send(self, text):
        body = text.encode('utf-8') if isinstance(text, str) else text
        auth = {'apiKey': self.api_key} if self.api_key else None

        r = self.req.post(urljoin(self.host, '/aliens/send'), data=body, params=auth)
        if r.status_code != 200:
            print('Unexpected server response:', file=sys.stderr)
            print('HTTP code:', r.status_code, file=sys.stderr)
            print('Response body:', r.text, file=sys.stderr)
        r.raise_for_status()
        return r.content


class SpaceClient:
    def __init__(self, api_host=API_HOST, api_key=None, player_key=None):
        self.tr = SpaceTransport(api_host, api_key=api_key)
        self.player_key = player_key
        self.codec = ConsCodec()

    def send(self, message):
        text = self.codec.encode(message)
        response = self.tr.send(text)
        return self.codec.decode(response)

    def ping(self):
        m = [0]
        return self.send(m)

    def create_server(self):
        m = [1, 0]
        return self.send(m)

    def join_server(self):
        m = [2, int(self.player_key), []]
        return self.send(m)

    def start_game(self, x):
        m = [3, int(self.player_key), (0,0,0,x)]
        return self.send(m)

    def send_commands(self, commands):
        m = [4, int(self.player_key), commands]
