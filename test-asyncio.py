#! /usr/bin/env python3

import asyncio

async def consume_items(arr):
  while arr:
    await asyncio.sleep(1)
    print(arr.pop())

class arange:

  def __init__(self, n):
    self.n = n
    self.i = 0

  def __aiter__(self):
    # In 3.5.0/3.5.1 this method should be async (deprecated after 3.5.2)
    return self

  async def __anext__(self):
    await asyncio.sleep(0.5)    # simulate some async job
    #if self.i % 3 == 2:
    #  # !!: we detected an error
    #  self.i += 1
    #  raise RuntimeError('xx')  # pass the exception to caller
    if self.i == self.n:
      raise StopAsyncIteration  # iteration is done
    i = self.i
    self.i += 1
    return i      # yield the current item


async def test():
  it = arange(10)
  while True:
    try:
      async for i in it:
        print(i)
      else:
        # if iteration finishes successfully, break.
        break
    except Exception as e:
      print('Exception: {}'.format(e.args))
      # continue the iteration.


loop = asyncio.get_event_loop()
#loop.run_until_complete(test())
loop.run_until_complete(consume_items([1, 2, 3]))


# vim: sts=2 sw=2 et
