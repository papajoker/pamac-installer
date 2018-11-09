#!/usr/bin/env python

import gi
gi.require_version('Pamac', '1.0')  # import xml /usr/share/gir-1.0/Pamac-1.0.gir
from gi.repository import GLib, Pamac


from PyQt5.QtCore import (QPoint, QSettings, QSize, Qt)
from PyQt5.QtGui import QIcon, QKeySequence
from PyQt5.QtWidgets import (QAction, QApplication, QMainWindow, QMessageBox, QTextEdit, QToolBar)
import sys
import re

class Commit:

    def __init__(self, db, post_message):
        self.data = None
        self.loop = None

        #self.statusBar = statusBar
        #self.text = text
        self.post_message = post_message

        self.transaction = self.transaction = Pamac.Transaction(database=db)

        self.transaction.connect("emit-action", self.on_emit_action, self.data)
        self.transaction.connect("emit-action-progress", self.on_emit_action_progress, self.data)
        self.transaction.connect("emit-hook-progress", self.on_emit_hook_progress, self.data)
        self.transaction.connect("emit-error", self.on_emit_error, self.data)
        self.transaction.connect("emit-warning", self.on_emit_warning, self.data)
        self.transaction.connect("finished", self.on_trans_finished, self.data)

    def __enter__(self):
        if not self.transaction.get_lock():
            raise Exception("pamac-system-daemon running")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.loop = GLib.MainLoop()
        return self

    def __exit__(self, type, value, traceback):
        try:
            self.loop.quit()
            self.transaction.unlock()
            self.transaction.quit_daemon()
        except:
            pass
        QApplication.restoreOverrideCursor()

    def run(self, to_install=[], to_remove=[], to_load=[]):
        if self.transaction.get_lock():
            self.transaction.start(to_install, to_remove, to_load, [], [], [])
            # launch a loop to wait for finished signal to be emitted
            self.loop.run()

    def on_trans_finished(self, transaction, success, data):
        print(success)
        self.post_message('END.', 6)
        self.loop.quit()

    def on_emit_error(self, transaction, message, details, details_length, data):
        #print("------")
        if details_length > 0:
            print(f"{message}:")
            for detail in details:
                print(detail)
                self.post_message(detail, 4)
        else:
            self.post_message(message, 4)
            print(message)
        self.loop.quit()
        transaction.unlock()
        transaction.quit_daemon()

    def on_emit_action(self, transaction, action, data):
        print("on_emit_action", action)
        self.post_message(action, 1)

    def on_emit_hook_progress(self, transaction, action, details, status, progress, data):
        #print(f"{action} {details} {status}")
        self.post_message(f"{action} {details} {status}", 3)


    def on_emit_action_progress(self, transaction, action, status, progress, data):
        print("on_emit_action_progress", f"{action} {status}")
        if not status.startswith("0"):
            self.post_message(f"::{action} {status}", 3)

    def on_emit_warning(self, transaction, message, data):
        print("on_emit_warning", message)
        self.post_message(message, 5)



class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.setWindowTitle("pamac installer QT example")

        #package name
        self.to_install = []
        #package name with -
        self.to_remove = []
        #package file
        self.to_load = []

        self.text = QTextEdit()
        self.setCentralWidget(self.text)
        self.createActions()
        self.createMenus()
        self.createToolBars()
        self.createStatusBar()
        self.setPacman()
        self.readSettings()
        self.commitAct.setEnabled(len(self.text.toPlainText().split()) > 0)

    def closeEvent(self, event):
        event.accept()
        self.writeSettings()

    def setPacman(self):
        self.config = Pamac.Config(conf_path="/etc/pamac.conf")
        self.db = Pamac.Database(config=self.config)

    def post_message(self, msg: str, status):
        switcher = {
            1: "-> ",
            2: ":: ",
            3: "   ",
            4: "!!! ",
            5: "! ",
            6: "",
        }   
        self.text.append(f"{switcher.get(status, '')}{msg}")
        self.statusBar().showMessage(msg, 2000)
        if status == 4:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "pamac", msg)

    def commit(self):
        """pacman commit"""
        self.parse_edit()
        self.text.setReadOnly(True)
        try:
            with Commit(self.db, self.post_message) as mycommit:
                mycommit.run(to_install=self.to_install, to_remove=self.to_remove, to_load=self.to_load  )
        except Exception as ex:
            print("transaction.get_lock(): False", "\nwait "+ex.args[0])
            QMessageBox.critical(self, "pamac", "ERROR: "+ex.args[0])
        self.text.setReadOnly(False)

    def about(self):
        QMessageBox.about(self, "About Application",
                "The <b>Application</b> example demonstrates how to write "
                "QT pamac applications, with python.")


    def createActions(self):
        self.commitAct = QAction(QIcon.fromTheme("arrow-right"), "&Commit", self,
                shortcut=QKeySequence.New, statusTip="commit packages",
                triggered=self.commit)

        self.exitAct = QAction(QIcon.fromTheme("application-exit"), "E&xit", self, shortcut="Ctrl+Q",
                statusTip="Exit the application", triggered=self.close)

        self.aboutAct = QAction("&About", self,
                statusTip="Show the application's About box",
                triggered=self.about)

        self.aboutQtAct = QAction("About &Qt", self,
                statusTip="Show the Qt library's About box",
                triggered=QApplication.instance().aboutQt)

    def createMenus(self):
        fileMenu = self.menuBar().addMenu("&Package")
        fileMenu.addAction(self.commitAct)
        self.menuBar().addSeparator()
        fileMenu = self.menuBar().addMenu("&Application")
        fileMenu.addAction(self.exitAct)
        helpMenu = self.menuBar().addMenu("&Help")
        helpMenu.addAction(self.aboutAct)
        helpMenu.addAction(self.aboutQtAct)

    def createToolBars(self):
        filetoolbar = QToolBar()
        if filetoolbar.iconSize().width() < 36:
            iconSize = QSize(36, 36)
            filetoolbar.setIconSize(iconSize)        
        self.addToolBar(Qt.LeftToolBarArea, filetoolbar)
        filetoolbar.setOrientation(Qt.Vertical)
        filetoolbar.addAction(self.commitAct)
        filetoolbar.addAction(self.exitAct)

    def createStatusBar(self):
        self.statusBar().showMessage("Ready")

    def readSettings(self):
        settings = QSettings("Trolltech", "Pamac installer")
        pos = settings.value("pos", QPoint(100, 100))
        size = settings.value("size", QSize(600, 400))
        self.resize(size)
        self.move(pos)

        self.to_install = []
        #package name with -
        self.to_remove = []
        #package file
        self.to_load = []
        for arg in sys.argv:
            if arg != sys.argv[0]:
                pkg = arg
                if pkg.startswith("-"):
                    pkg = pkg[1:]
                pkg = self.db.get_pkg_details(pkg, "", False)
                info = pkg.props.desc
                if info:
                    info = f"({info})"
                self.text.append(f"{arg}    {info}")

    def parse_edit(self):
        pkgs = self.text.toPlainText()
        # remove descriptions
        pkgs = re.sub(r"\(.*\)", "", pkgs)
        #TODO remove text after "--> Preparing..." if reload
        pkgs = pkgs.split()
        for pkg in pkgs:
            if pkg.startswith("-"):
                self.to_remove.append(pkg[1:])
            elif pkg.startswith("/"):
                self.to_load.append(pkg)
            elif pkg.startswith("file:/"):
                self.to_load.append(pkg[6:])
            else:
                self.to_install.append(pkg)
        print("self.to_install", self.to_install)
        print("self.to_remove", self.to_remove)
        print("self.to_load", self.to_load)

    def writeSettings(self):
        settings = QSettings("Trolltech", "Pamac installer")
        settings.setValue("pos", self.pos())
        settings.setValue("size", self.size())

def usage():
    """help"""
    print("pamac-installer.py [list of packages]")
    print("for remove add -")
    print("example: pamac-installer.py vlc -vi (remove vi and install vlc)")
    exit(0)

if __name__ == '__main__':

    if any({"-h", "--help"} & {*sys.argv}):
        usage()

    app = QApplication(sys.argv)
    mainwin = MainWindow()
    mainwin.show()
    sys.exit(app.exec_())
