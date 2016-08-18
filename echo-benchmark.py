#! /usr/bin/env python3

'''
A micro-benchmark to compare different networking schemes.
'''

import asyncio
import os
import signal
import socket
import socketserver
from statistics import mean
import multiprocessing
import threading
import time
import uvloop

repeat = 30
trials = 10
backlog = 5
payload_sz = None
message = None


# coroutine version
async def echo_server(reader, writer):
    msg = await reader.readexactly(payload_sz)
    writer.write(msg)
    await writer.drain()

# Protocol version
class EchoServerProtocol(asyncio.Protocol):
    def connection_made(self, transport):
        self.transport = transport

    def data_received(self, data):
        self.transport.write(data)

# socketserver version
class EchoServerHandler(socketserver.BaseRequestHandler):
    def handle(self):
        remaining = payload_sz
        data = []
        while remaining > 0:
            data.append(self.request.recv(payload_sz))
            remaining -= len(data[-1])
        for d in data:
            self.request.sendall(d)
        assert b'' == self.request.recv(1)
        self.request.close()

class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    pass


class SequentialServerProcess(multiprocessing.Process):

    def __init__(self, *args, cpu=1, **kwargs):
        super().__init__(*args, **kwargs)
        self.cpu = cpu

    def run(self):
        os.sched_setaffinity(self.pid, [self.cpu])
        server = socketserver.TCPServer(('127.0.0.1', 8888), EchoServerHandler, bind_and_activate=False)
        server.request_queue_size = backlog
        server.allow_reuse_address = True
        server.server_bind()
        server.server_activate()
        server.serve_forever()

class ThreadedServerProcess(multiprocessing.Process):
    
    def __init__(self, *args, cpu=1, **kwargs):
        super().__init__(*args, **kwargs)
        self.cpu = cpu

    def run(self):
        os.sched_setaffinity(self.pid, [self.cpu])
        server = ThreadedTCPServer(('127.0.0.1', 8888), EchoServerHandler, bind_and_activate=False)
        server.request_queue_size = backlog
        server.allow_reuse_address = True
        server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        server.server_bind()
        server.server_activate()
        server.serve_forever()


class AsyncCoroServerProcess(multiprocessing.Process):

    def __init__(self, *args, cpu=1, **kwargs):
        super().__init__(*args, **kwargs)
        self.cpu = cpu

    def run(self):
        os.sched_setaffinity(self.pid, [self.cpu])
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        server = self.loop.run_until_complete(
            asyncio.start_server(echo_server,
                                 '127.0.0.1', 8888,
                                 backlog=backlog,
                                 reuse_address=True,
                                 reuse_port=True))
        try:
            self.loop.run_forever()
        finally:
            server.close()
            self.loop.run_until_complete(server.wait_closed())
            self.loop.close()

class AsyncProtoServerProcess(multiprocessing.Process):

    def __init__(self, *args, cpu=1, **kwargs):
        super().__init__(*args, **kwargs)
        self.cpu = cpu

    def run(self):
        os.sched_setaffinity(self.pid, [self.cpu])
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        server = self.loop.run_until_complete(
            self.loop.create_server(EchoServerProtocol,
                                  '127.0.0.1', 8888,
                                  backlog=backlog,
                                  reuse_address=True,
                                  reuse_port=True))
        try:
            self.loop.run_forever()
        finally:
            server.close()
            self.loop.run_until_complete(server.wait_closed())
            self.loop.close()


class SequentialClientProcess(multiprocessing.Process):

    def __init__(self, *args, cpu=0, **kwargs):
        super().__init__(*args, **kwargs)
        self.cpu = cpu

    def run(self):
        os.sched_setaffinity(self.pid, [self.cpu])
        time.sleep(0.01)
        for _ in range(repeat):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.connect(('127.0.0.1', 8888))
                sock.sendall(message)
                remaining = payload_sz
                data = []
                while remaining > 0:
                    data.append(sock.recv(payload_sz))
                    remaining -= len(data[-1])
                sock.shutdown(socket.SHUT_RDWR)


def run(server_proc_cls, num_servers, client_proc_cls, num_clients):
    t = []
    for _ in range(trials):
        server_procs = []
        client_procs = []
        for i in range(num_servers):
            server = server_proc_cls(cpu=i)
            server.daemon = True
            server_procs.append(server)
            server.start()
        t_start = time.monotonic()
        for i in range(num_clients):
            client = client_proc_cls(cpu=num_servers + i)
            client_procs.append(client)
            client.start()
        for client in client_procs:
            client.join()
        t_end = time.monotonic()
        for server in server_procs:
            server.terminate()
        for server in server_procs:
            server.join()
        t.append(t_end - t_start - 0.01)
    print('{0}[{1}] <=> {2}[{3}] - '.format(server_proc_cls.__name__, num_servers, client_proc_cls.__name__, num_clients), end='')
    print('Elapsed time: avg {:.6f} sec. (min/max {:.6f}/{:.6f})'.format(mean(t), min(t), max(t)))


if __name__ == '__main__':
    # Apply uvloop.
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

    for payload_sz in [128, 512, 1024, 2048]:
    #for payload_sz in [4096, 8192, 16384]:
    #for payload_sz in [262144, 524288]:
    #for payload_sz in [1048576]:
        message = b'*' * payload_sz
        print('payload_sz: {:,} bytes'.format(payload_sz))
        run(SequentialServerProcess, 1, SequentialClientProcess, 3)
        run(ThreadedServerProcess, 1, SequentialClientProcess, 3)
        #run(AsyncCoroServerProcess, 1, SequentialClientProcess, 3)
        #run(AsyncProtoServerProcess, 1, SequentialClientProcess, 3)

# vim: sts=4 sw=4 et
