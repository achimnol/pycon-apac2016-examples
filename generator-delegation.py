#! /usr/bin/env python3

# Ref: http://stackoverflow.com/questions/9708902/

import os


def read_data():
  for i in range(5):
    print('reading {}'.format(i))
    yield i

def write_data():
  while True:
    data = (yield)
    print('recording {}'.format(data))


print('-----------------------')
# With simple generators only, we need to write multiple different codes for
# different use of the generator protocol.

def read_wrapper(coro):
  for value in coro:
    yield value

def write_wrapper(coro):
  coro.send(None)
  while True:
    try:
      ret = (yield)
    except Exception as e:
      coro.throw(e)
    except StopIteration:
      pass
    else:
      coro.send(ret)


values = []
reader = read_wrapper(read_data())
for v in reader:
  values.append(v)

writer = write_wrapper(write_data())
writer.send(None)
for v in values:
  writer.send(v)


print('-----------------------')
# With generator delegation, all the generator protocol details are
# auto-magically handled by Python.

def delegate(coro):
  yield from coro

values = []
reader = delegate(read_data())
for v in reader:
  values.append(v)

writer = delegate(write_data())
writer.send(None)
for v in values:
  writer.send(v)


print('-----------------------')
# Even with exceptions, it works well!

def read_data():
  i = 0
  while True:
    if i == 3:
      i += 1 # skip to next
      print('throing at 3, continuing to 4')
      raise RuntimeError
    if i == 5:
      return
    print('reading {}'.format(i))
    yield i
    i += 1

def write_data():
  while True:
    try:
      data = (yield)
    except RuntimeError:
      print('error! skipping the record')
    else:
      print('recording {}'.format(data))

values = []
reader = delegate(read_data())
while True:
  try:
    v = next(reader)
    values.append(v)
  except RuntimeError:
    print('skip errorneous data')
  except StopIteration:
    print('stop')
    break

print('...')
writer = delegate(write_data())
writer.send(None)
for v in values:
  if v == 2:
    writer.throw(RuntimeError)
  else:
    writer.send(v)




# vim: sts=2 sw=2 et
