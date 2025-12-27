# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'MainWindow.ui'
##
## Created by: Qt User Interface Compiler version 6.5.1
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QComboBox, QFrame, QGridLayout,
    QHBoxLayout, QHeaderView, QLabel, QMainWindow,
    QPushButton, QSizePolicy, QSpacerItem, QStatusBar,
    QTableView, QVBoxLayout, QWidget)
import resources_rc

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(1172, 711)
        icon = QIcon()
        icon.addFile(u":/icon/res/icon.png", QSize(), QIcon.Normal, QIcon.Off)
        MainWindow.setWindowIcon(icon)
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.verticalLayout_4 = QVBoxLayout(self.centralwidget)
        self.verticalLayout_4.setObjectName(u"verticalLayout_4")
        self.horizontalLayout = QHBoxLayout()
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.label = QLabel(self.centralwidget)
        self.label.setObjectName(u"label")
        self.label.setMinimumSize(QSize(75, 0))
        self.label.setMaximumSize(QSize(75, 16777215))
        font = QFont()
        font.setPointSize(11)
        font.setBold(True)
        self.label.setFont(font)

        self.horizontalLayout.addWidget(self.label)

        self.cmbSelectPN = QComboBox(self.centralwidget)
        self.cmbSelectPN.setObjectName(u"cmbSelectPN")
        self.cmbSelectPN.setMinimumSize(QSize(0, 35))
        font1 = QFont()
        font1.setPointSize(11)
        self.cmbSelectPN.setFont(font1)

        self.horizontalLayout.addWidget(self.cmbSelectPN)

        self.btnMoveTodo = QPushButton(self.centralwidget)
        self.btnMoveTodo.setObjectName(u"btnMoveTodo")
        self.btnMoveTodo.setMinimumSize(QSize(0, 38))
        self.btnMoveTodo.setMaximumSize(QSize(140, 16777215))
        font2 = QFont()
        font2.setBold(True)
        self.btnMoveTodo.setFont(font2)
        icon1 = QIcon()
        icon1.addFile(u":/icon/res/todo.png", QSize(), QIcon.Normal, QIcon.Off)
        self.btnMoveTodo.setIcon(icon1)

        self.horizontalLayout.addWidget(self.btnMoveTodo)


        self.verticalLayout_4.addLayout(self.horizontalLayout)

        self.horizontalLayout_2 = QHBoxLayout()
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.verticalLayout_2 = QVBoxLayout()
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.tblImages = QTableView(self.centralwidget)
        self.tblImages.setObjectName(u"tblImages")
        self.tblImages.setMinimumSize(QSize(245, 0))
        self.tblImages.setMaximumSize(QSize(270, 16777215))

        self.verticalLayout_2.addWidget(self.tblImages)


        self.horizontalLayout_2.addLayout(self.verticalLayout_2)

        self.line = QFrame(self.centralwidget)
        self.line.setObjectName(u"line")
        self.line.setFrameShape(QFrame.VLine)
        self.line.setFrameShadow(QFrame.Sunken)

        self.horizontalLayout_2.addWidget(self.line)

        self.verticalLayout_3 = QVBoxLayout()
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.line_2 = QFrame(self.centralwidget)
        self.line_2.setObjectName(u"line_2")
        self.line_2.setFrameShape(QFrame.HLine)
        self.line_2.setFrameShadow(QFrame.Sunken)

        self.verticalLayout_3.addWidget(self.line_2)

        self.lblTitle = QLabel(self.centralwidget)
        self.lblTitle.setObjectName(u"lblTitle")
        self.lblTitle.setMinimumSize(QSize(0, 30))
        self.lblTitle.setMaximumSize(QSize(16777215, 30))
        self.lblTitle.setFont(font)
        self.lblTitle.setFrameShape(QFrame.NoFrame)
        self.lblTitle.setAlignment(Qt.AlignBottom|Qt.AlignHCenter)

        self.verticalLayout_3.addWidget(self.lblTitle)

        self.lblComment = QLabel(self.centralwidget)
        self.lblComment.setObjectName(u"lblComment")
        self.lblComment.setAlignment(Qt.AlignCenter)

        self.verticalLayout_3.addWidget(self.lblComment)

        self.gridLayout = QGridLayout()
        self.gridLayout.setObjectName(u"gridLayout")
        self.imgCS = QLabel(self.centralwidget)
        self.imgCS.setObjectName(u"imgCS")
        self.imgCS.setMinimumSize(QSize(300, 300))
        self.imgCS.setFrameShape(QFrame.Box)
        self.imgCS.setAlignment(Qt.AlignCenter)

        self.gridLayout.addWidget(self.imgCS, 3, 0, 1, 1)

        self.imgSS = QLabel(self.centralwidget)
        self.imgSS.setObjectName(u"imgSS")
        self.imgSS.setMinimumSize(QSize(300, 300))
        self.imgSS.setFrameShape(QFrame.Box)
        self.imgSS.setAlignment(Qt.AlignCenter)

        self.gridLayout.addWidget(self.imgSS, 3, 1, 1, 1)

        self.label_5 = QLabel(self.centralwidget)
        self.label_5.setObjectName(u"label_5")
        self.label_5.setMaximumSize(QSize(16777215, 25))
        self.label_5.setAlignment(Qt.AlignCenter)

        self.gridLayout.addWidget(self.label_5, 2, 0, 1, 1)

        self.label_6 = QLabel(self.centralwidget)
        self.label_6.setObjectName(u"label_6")
        self.label_6.setMaximumSize(QSize(16777215, 25))
        self.label_6.setAlignment(Qt.AlignCenter)

        self.gridLayout.addWidget(self.label_6, 2, 1, 1, 1)


        self.verticalLayout_3.addLayout(self.gridLayout)

        self.horizontalLayout_3 = QHBoxLayout()
        self.horizontalLayout_3.setObjectName(u"horizontalLayout_3")
        self.horizontalSpacer_2 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_3.addItem(self.horizontalSpacer_2)

        self.btnMarkOK = QPushButton(self.centralwidget)
        self.btnMarkOK.setObjectName(u"btnMarkOK")
        self.btnMarkOK.setMinimumSize(QSize(150, 40))
        self.btnMarkOK.setMaximumSize(QSize(150, 16777215))

        self.horizontalLayout_3.addWidget(self.btnMarkOK)

        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_3.addItem(self.horizontalSpacer)

        self.btnMarkSection = QPushButton(self.centralwidget)
        self.btnMarkSection.setObjectName(u"btnMarkSection")
        self.btnMarkSection.setMinimumSize(QSize(150, 40))
        self.btnMarkSection.setMaximumSize(QSize(150, 16777215))

        self.horizontalLayout_3.addWidget(self.btnMarkSection)

        self.horizontalSpacer_4 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_3.addItem(self.horizontalSpacer_4)

        self.btnMarkDelete = QPushButton(self.centralwidget)
        self.btnMarkDelete.setObjectName(u"btnMarkDelete")
        self.btnMarkDelete.setMinimumSize(QSize(150, 40))
        self.btnMarkDelete.setMaximumSize(QSize(150, 16777215))

        self.horizontalLayout_3.addWidget(self.btnMarkDelete)

        self.horizontalSpacer_3 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_3.addItem(self.horizontalSpacer_3)


        self.verticalLayout_3.addLayout(self.horizontalLayout_3)

        self.verticalLayout_3.setStretch(3, 1)

        self.horizontalLayout_2.addLayout(self.verticalLayout_3)

        self.horizontalLayout_2.setStretch(2, 1)

        self.verticalLayout_4.addLayout(self.horizontalLayout_2)

        MainWindow.setCentralWidget(self.centralwidget)
        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName(u"statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.retranslateUi(MainWindow)

        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"MainWindow", None))
        self.label.setText(QCoreApplication.translate("MainWindow", u"\u6d4b\u91cf\u578b\u53f7\uff1a", None))
        self.btnMoveTodo.setText(QCoreApplication.translate("MainWindow", u"\u53d1\u9001\u5230\u677f\u539a\u5206\u6790", None))
        self.lblTitle.setText(QCoreApplication.translate("MainWindow", u"\u677f\u539a\u56fe\u7247", None))
        self.lblComment.setText("")
        self.imgCS.setText("")
        self.imgSS.setText("")
        self.label_5.setText(QCoreApplication.translate("MainWindow", u"\u6b63\u9762", None))
        self.label_6.setText(QCoreApplication.translate("MainWindow", u"\u53cd\u9762", None))
        self.btnMarkOK.setText(QCoreApplication.translate("MainWindow", u"\u2705 \u6807\u8bb0\u4e3aOK\u677f", None))
        self.btnMarkSection.setText(QCoreApplication.translate("MainWindow", u"\u2b55 \u6807\u8bb0\u4e3a\u5207\u7247\u677f", None))
        self.btnMarkDelete.setText(QCoreApplication.translate("MainWindow", u"\u274c \u5220\u9664\u5f53\u524d\u5f02\u5e38\u56fe\u7247", None))
    # retranslateUi

