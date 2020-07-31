#!/usr/bin/env python
import arrival
import requests
import sys
from urllib.parse import urljoin
import logging

logging.basicConfig(level=logging.DEBUG)


class Transport:
    def __init__(self, url, api_key=None):
        self.url = url
        self.api_key = api_key
        self.req = requests.Session()

    def send(self, text):
        body = text.encode('utf-8')
        auth = {'apiKey': self.api_key} if self.api_key else None

        r = self.req.post(urljoin(self.url, '/aliens/send'), data=body, params=auth)
        if r.status_code != 200:
            print('Unexpected server response:')
            print('HTTP code:', r.status_code)
            print('Response body:', r.text)
            exit(2)
        print('Server response:', r.text)
        return r.text


class Client:
    def __init__(self, url, player_key, api_key=None):
        self.tr = Transport(url, api_key=api_key)
        self.player_key = player_key
        self.codec = arrival.ConsCodec()

    def send(self, message):
        print(repr(message))
        text = self.codec.encode(message)
        response = self.tr.send(text)
        r = self.codec.decode(response)
        print(repr(r))
        if r == [0]:
            raise Exception('server [0]')
        return r

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
        return self.send(m)


class Player:
    pass

def main(url, player=None):
    print('ServerUrl: %s; PlayerKey: %s' % (url, player))

    cli = Client(url=url, player_key=player, api_key=None)

    if not player:
        _, ((_, attack_key), (_, defend_key)) = cli.create_server()
        print('attack key:', attack_key)
        print('defend key:', defend_key)
        cli.player_key = attack_key

    cli.join_server()

    cli.start_game(1 if player else 2)

    # (1, gameStage, staticGameInfo, gameState)

    while True:
        cli.send_commands([])


if __name__ == '__main__':
    main(*sys.argv[1:])
