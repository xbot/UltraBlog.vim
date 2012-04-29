#!/usr/bin/python

import gtk
import webkit

class UBPreviewer(gtk.Window):
    def __init__(self):
        super(UBPreviewer, self).__init__()
        self.connect("destroy", self.onDestroy)
        self.set_size_request(800, 600)
        self.set_position(gtk.WIN_POS_CENTER)
        self.set_title(_('Previewer for UltraBlog.vim'))

        vbox = gtk.VBox()
        self.add(vbox)

        self.viewer = webkit.WebView()
        self.viewer.connect('title-changed', self.onTitleChanged)
        self.viewer.connect('load-progress-changed', self.onLoadProgressChanged)
        self.viewer.connect('load-started', self.onLoadStarted)
        self.viewer.connect('load-finished', self.onLoadFinished)

        scroller = gtk.ScrolledWindow()
        scroller.add(self.viewer)
        vbox.pack_start(scroller)

        self.progress = gtk.ProgressBar()
        vbox.pack_start(self.progress, False)

        self.show_all()

    def open(self, url):
        self.viewer.open(url)
    
    def onTitleChanged(self, webview, frame, title):
        self.set_title(title)

    def onLoadProgressChanged(self, webview, amount):
        self.progress.set_fraction(amount/100.0)

    def onLoadStarted(self, webview, frame):
        self.progress.set_visible(True)

    def onLoadFinished(self, webview, frame):
        self.progress.set_visible(False)

    def onDestroy(self, w=None, data=None):
        ''' Destroy app
        '''
        gtk.main_quit()

def open(url):
    app = UBPreviewer()
    app.open(url)
    gtk.main()

if __name__ == '__main__':
    pass
