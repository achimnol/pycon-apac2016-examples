#! /usr/bin/env python3

import asyncio
import time

'''
def myrange(n):
  while True:
    time.sleep(0.5)
    if i == n:
      break
    yield i
    i += 1
'''

class myrange:

  def __init__(self, n):
    self.n = n
    self.i = 0

  def __iter__(self):
    return self

  def __next__(self):
    time.sleep(0.5)
    if self.i == self.n:
      raise StopIteration
    i = self.i
    self.i += 1
    return i

'''
async def arange(n):
  while True:
    await time.sleep(0.5)
    if i == n:
      break
    yield i  # not supported yet!
    i += 1
'''

class arange:

  def __init__(self, n):
    self.n = n
    self.i = 0

  def __aiter__(self):
    return self

  async def __anext__(self):
    await asyncio.sleep(0.5)
    if self.i == self.n:
      raise StopAsyncIteration
    i = self.i
    self.i += 1
    return i


def run():
  for i in myrange(10):
    print(i)
run()


async def run():
  async for i in arange(10):
    print(i)

loop = asyncio.get_event_loop()
loop.run_until_complete(run())


# vim: sts=2 sw=2 et
