#! /usr/bin/env python3

'''
A micro-benchmark to compare different networking schemes.
'''

import asyncio
import os
import signal
import socket
from statistics import mean
import threading
import multiprocessing
import time
import uvloop

import ctypes, ctypes.util
SYS_gettid = 186
libc = ctypes.cdll.LoadLibrary(ctypes.util.find_library('c'))
def gettid():
    #return int(libc.syscall(SYS_gettid))
    return os.getpid()

def noop(*args, **kwargs):
    pass
os.sched_setaffinity = noop

repeat = 10
trials = 10
backlog = 256
payload_sz = 100
message = b'*' * payload_sz


async def echo_server(reader, writer):
    msg = await reader.read(payload_sz)
    writer.write(msg)

class EchoServerProtocol(asyncio.Protocol):
    def connection_made(self, transport):
        self.transport = transport

    def data_received(self, data):
        self.transport.write(data)


class AsyncServerThread(multiprocessing.Process):
#class AsyncServerThread(threading.Thread):

    def __init__(self, *args, cpu=1, **kwargs):
        super().__init__(*args, **kwargs)
        self.cpu = cpu

    def run(self):
        os.sched_setaffinity(gettid(), [self.cpu])
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

class AsyncProtoServerThread(multiprocessing.Process):

    def __init__(self, *args, cpu=1, **kwargs):
        super().__init__(*args, **kwargs)
        self.cpu = cpu

    def run(self):
        os.sched_setaffinity(gettid(), [self.cpu])
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

class SequentialServerThread(multiprocessing.Process):

    def __init__(self, *args, cpu=1, **kwargs):
        super().__init__(*args, **kwargs)
        self.cpu = cpu

    def run(self):
        os.sched_setaffinity(gettid(), [self.cpu])
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, True)
        sock.bind(('127.0.0.1', 8888))
        sock.listen(backlog)
        for _ in range(repeat):
            client, peer_addr = sock.accept()
            remaining = payload_sz
            data = []
            while remaining > 0:
                data.append(client.recv(payload_sz))
                remaining -= len(data[-1])
            client.send(b''.join(data))
            client.close()
        sock.close()


class AsyncClientProcess(multiprocessing.Process):

    def __init__(self, *args, cpu=0, **kwargs):
        super().__init__(*args, **kwargs)
        self.cpu = cpu

    def run(self):
        os.sched_setaffinity(self.pid, [self.cpu])
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self.repeat_echo())
        finally:
            self.loop.close()

    async def repeat_echo(self):
        asyncio.sleep(0.01)
        for i in range(repeat):
            reader, writer = await asyncio.open_connection('127.0.0.1', 8888)
            writer.write(message)
            data = await reader.read(payload_sz)
            assert data == message
            writer.close()


class AsyncProtoClientProcess(multiprocessing.Process):

    def __init__(self, *args, cpu=0, **kwargs):
        super().__init__(*args, **kwargs)
        self.cpu = cpu

    class EchoClientProtocol(asyncio.Protocol):
        def __init__(self, loop=None):
            self.loop = loop

        def connection_made(self, transport):
            transport.write(message)

        def data_received(self, data):
            assert data == message

        def connection_lost(self, exc):
            self.loop.stop()

    def run(self):
        os.sched_setaffinity(self.pid, [self.cpu])
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self.repeat_echo())
        finally:
            self.loop.close()

    async def repeat_echo(self):
        asyncio.sleep(0.01)
        for i in range(repeat):
            await loop.create_connection(
                lambda: EchoClientProtocol(),
                '127.0.0.1', 8888)

class SequentialClientProcess(multiprocessing.Process):

    def __init__(self, *args, cpu=0, **kwargs):
        super().__init__(*args, **kwargs)
        self.cpu = cpu

    def run(self):
        os.sched_setaffinity(self.pid, [self.cpu])
        time.sleep(0.01)
        for _ in range(repeat):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(('127.0.0.1', 8888))
            sock.send(message)
            remaining = payload_sz
            data = []
            while remaining > 0:
                data.append(sock.recv(payload_sz))
                remaining -= len(data[-1])
            assert b''.join(data) == message
            sock.close()


if __name__ == '__main__':

    t = []
    for _ in range(trials):
        server_thread = SequentialServerThread(cpu=1)
        server_thread.start()
        client_threads = [SequentialClientProcess(cpu=0), SequentialClientProcess(cpu=3)]
        for c in client_threads:
            c.start()
        t_start = time.monotonic()
        for c in client_threads:
            c.join()
        t_end = time.monotonic()
        server_thread.join()
        t.append(t_end - t_start)
    print('seq.server + seq.client2 - ', end='')
    print('Elapsed time: avg {:.6f} sec. (min/max {:.6f}/{:.6f})'.format(mean(t), min(t), max(t)))

    t = []
    for _ in range(trials):
        server_threads = [SequentialServerThread(cpu=1), SequentialServerThread(cpu=2)]
        for s in server_threads:
            s.start()
        client_threads = [SequentialClientProcess(cpu=0), SequentialClientProcess(cpu=3)]
        for c in client_threads:
            c.start()
        t_start = time.monotonic()
        for c in client_threads:
            c.join()
        t_end = time.monotonic()
        for s in server_threads:
            s.terminate()
        for s in server_threads:
            s.join()
        t.append(t_end - t_start)
    print('seq.server2 + async.client2 - ', end='')
    print('Elapsed time: avg {:.6f} sec. (min/max {:.6f}/{:.6f})'.format(mean(t), min(t), max(t)))

    t = []
    for _ in range(trials):
        server_thread = AsyncServerThread(cpu=1)
        server_thread.start()
        client_threads = [SequentialClientProcess(cpu=0), SequentialClientProcess(cpu=3)]
        for c in client_threads:
            c.start()
        t_start = time.monotonic()
        for c in client_threads:
            c.join()
        t_end = time.monotonic()
        #server_thread.loop.call_soon_threadsafe(server_thread.loop.stop)
        server_thread.terminate()
        server_thread.join()
        t.append(t_end - t_start)
    print('async.server + seq.client2 - ', end='')
    print('Elapsed time: avg {:.6f} sec. (min/max {:.6f}/{:.6f})'.format(mean(t), min(t), max(t)))

    t = []
    for _ in range(trials):
        server_threads = [AsyncServerThread(cpu=1), AsyncServerThread(cpu=2)]
        for s in server_threads:
            s.start()
        client_threads = [SequentialClientProcess(cpu=0), SequentialClientProcess(cpu=3)]
        for c in client_threads:
            c.start()
        t_start = time.monotonic()
        for c in client_threads:
            c.join()
        t_end = time.monotonic()
        for s in server_threads:
            s.terminate()
        for s in server_threads:
            s.join()
        t.append(t_end - t_start)
    print('async.server2 + seq.client2 - ', end='')
    print('Elapsed time: avg {:.6f} sec. (min/max {:.6f}/{:.6f})'.format(mean(t), min(t), max(t)))

    t = []
    for _ in range(trials):
        server_thread = AsyncProtoServerThread(cpu=1)
        server_thread.start()
        client_threads = [SequentialClientProcess(cpu=0), SequentialClientProcess(cpu=3)]
        for c in client_threads:
            c.start()
        t_start = time.monotonic()
        for c in client_threads:
            c.join()
        t_end = time.monotonic()
        #server_thread.loop.call_soon_threadsafe(server_thread.loop.stop)
        server_thread.terminate()
        server_thread.join()
        t.append(t_end - t_start)
    print('asyncP.server + seq.client2 - ', end='')
    print('Elapsed time: avg {:.6f} sec. (min/max {:.6f}/{:.6f})'.format(mean(t), min(t), max(t)))

    t = []
    for _ in range(trials):
        server_threads = [AsyncProtoServerThread(cpu=1), AsyncProtoServerThread(cpu=2)]
        for s in server_threads:
            s.start()
        client_threads = [SequentialClientProcess(cpu=0), SequentialClientProcess(cpu=3)]
        for c in client_threads:
            c.start()
        t_start = time.monotonic()
        for c in client_threads:
            c.join()
        t_end = time.monotonic()
        for s in server_threads:
            #s.loop.call_soon_threadsafe(s.loop.stop)
            s.terminate()
        for s in server_threads:
            s.join()
        t.append(t_end - t_start)
    print('asyncP.server2 + seq.client2 - ', end='')
    print('Elapsed time: avg {:.6f} sec. (min/max {:.6f}/{:.6f})'.format(mean(t), min(t), max(t)))

    #t = []
    #for _ in range(trials):
    #    server_thread = AsyncServerThread()
    #    client_thread = AsyncClientProcess()
    #    server_thread.start()
    #    client_thread.start()
    #    t_start = time.monotonic()
    #    client_thread.join()
    #    t_end = time.monotonic()
    #    server_thread.loop.call_soon_threadsafe(server_thread.loop.stop)
    #    server_thread.join()
    #    t.append(t_end - t_start)
    #print('async.server + async.client - ', end='')
    #print('Elapsed time: avg {:.6f} sec. (min/max {:.6f}/{:.6f})'.format(mean(t), min(t), max(t)))

# vim: sts=4 sw=4 et
