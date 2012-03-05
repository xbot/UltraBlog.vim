#!/usr/bin/env python

class UBEventQueue:
    queue = []
    listeners = []

    @classmethod
    def fireEvent(cls, evt):
        cls.queue.append(evt)

    @classmethod
    def processEvents(cls):
        while len(cls.queue)>0:
            evt = cls.queue.pop()
            for listener in cls.listeners:
                if listener.isTarget(evt):
                    listener.processEvent(evt)

    @classmethod
    def registerListener(cls, lsnr):
        cls.listeners.append(lsnr)

if __name__ == '__main__':
    pass
