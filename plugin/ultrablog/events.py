#!/usr/bin/env python

class UBEvent:
    def __init__(self, srcObj):
        self.srcObj = srcObj

class UBDebugEvent(UBEvent): pass

class UBTmplDelEvent(UBEvent): pass
class UBTmplSaveEvent(UBEvent): pass

class UBLocalPostDelEvent(UBEvent): pass
class UBRemotePostDelEvent(UBEvent): pass
class UBPostSendEvent(UBEvent): pass
class UBPostSaveEvent(UBEvent): pass

class UBViewEnterEvent(UBEvent): pass

if __name__ == '__main__':
    pass
