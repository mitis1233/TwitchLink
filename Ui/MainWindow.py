from Core.App import App
from Core.Updater import Updater
from Core.Ui import *
from Services.Messages import Messages
from Services.Image.Loader import ImageLoader
from Services.Document import DocumentData, DocumentButtonData
from Services.Logging.ErrorDetector import ErrorDetector, ErrorHandlers
from Download.DownloadManager import DownloadManager
from Ui.Components.Operators.NavigationBar import NavigationBar
from Ui.Components.Pages.SearchPage import SearchPage
from Ui.Components.Pages.DownloadsPage import DownloadsPage
from Ui.Components.Pages.AccountPage import AccountPage
from Ui.Components.Pages.InformationPage import InformationPage
from Ui.Components.Widgets.ProgressDialog import ProgressDialog


class MainWindow(QtWidgets.QMainWindow, UiFile.mainWindow, WindowGeometryManager):
    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent=parent)
        App.appStarted.connect(self.start, QtCore.Qt.QueuedConnection)

    def start(self):
        if DB.setup.needSetup():
            if Ui.Setup().exec():
                App.restart()
            else:
                App.exit()
        else:
            Ui.Loading().exec()
            self.loadWindowGeometry()
            self.loadComponents()
            self.setup()

    def loadComponents(self):
        self.setWindowIcon(QtGui.QIcon(Icons.APP_LOGO_ICON))
        self.actionGettingStarted.triggered.connect(self.gettingStarted)
        self.actionAbout.triggered.connect(self.openAbout)
        self.actionTermsOfService.triggered.connect(self.openTermsOfService)
        self.actionSponsor.triggered.connect(self.sponsor)
        self.navigationBar = NavigationBar(self.navigationArea, parent=self)
        self.navigationBar.focusChanged.connect(self.onFocusChange)
        self.searchPageObject = self.navigationBar.addPage(self.searchPageButton, self.searchPage, icon=Icons.SEARCH_ICON)
        self.downloadsPageObject = self.navigationBar.addPage(self.downloadsPageButton, self.downloadsPage, icon=Icons.DOWNLOAD_ICON)
        self.accountPageObject = self.navigationBar.addPage(self.accountPageButton, self.accountPage, icon=Icons.ACCOUNT_ICON)
        self.settingsPageObject = self.navigationBar.addPage(self.settingsPageButton, self.settingsPage, icon=Icons.SETTINGS_ICON)
        self.informationPageObject = self.navigationBar.addPage(self.informationPageButton, self.informationPage, icon=Icons.INFO_ICON)
        self.search = SearchPage(self.searchPageObject, parent=self)
        self.search.accountPageShowRequested.connect(self.accountPageObject.show)
        self.searchPage.layout().addWidget(self.search)
        self.downloads = DownloadsPage(self.downloadsPageObject, parent=self)
        self.downloads.accountPageShowRequested.connect(self.accountPageObject.show)
        self.downloads.appShutdownRequested.connect(self.shutdown)
        self.downloads.systemShutdownRequested.connect(self.shutdownSystem)
        self.downloadsPage.layout().addWidget(self.downloads)
        self.account = AccountPage(self.accountPageObject, parent=self)
        self.accountPage.layout().addWidget(self.account)
        self.settings = Ui.Settings(parent=self)
        self.settings.restartRequired.connect(self.restart)
        self.settingsPage.layout().addWidget(self.settings)
        self.information = InformationPage(self.informationPageObject, parent=self)
        self.information.accountRefreshRequested.connect(self.account.refreshAccount)
        self.information.appShutdownRequested.connect(self.shutdown)
        self.informationPage.layout().addWidget(self.information)

    def setup(self):
        status = Updater.status.getStatus()
        if status == Updater.status.CONNECTION_FAILURE:
            self.show()
            self.info(*Messages.INFO.SERVER_CONNECTION_FAILED)
            self.shutdown()
            return
        elif status == Updater.status.UNEXPECTED_ERROR:
            self.show()
            self.info(*Messages.INFO.UNEXPECTED_ERROR)
            self.shutdown()
            return
        elif status == Updater.status.UNAVAILABLE:
            self.information.showDocument(
                DocumentData(
                    title=T("warning"),
                    content=Updater.status.operationalInfo or T("#{appName} is currently unavailable.", appName=Config.APP_NAME),
                    contentType=Updater.status.operationalInfoType if Updater.status.operationalInfo else "text",
                    modal=True,
                    buttons=[
                        DocumentButtonData(text="ok", action=self.shutdown, default=True)
                    ]
                )
            )
        elif status != Updater.status.AVAILABLE:
            updateInfo = self.information.showDocument(
                DocumentData(
                    title=T("recommended-update" if status == Updater.status.UPDATE_FOUND else "required-update"),
                    content=Updater.status.version.updateNote or f"{T('#A new version of {appName} has been released!', appName=Config.APP_NAME)}\n\n[{Config.APP_NAME} {Updater.status.version.latestVersion}]",
                    contentType=Updater.status.version.updateNoteType if Updater.status.version.updateNote else "text",
                    modal=status == Updater.status.UPDATE_REQUIRED,
                    buttons=[
                        DocumentButtonData(text=T("update"), action=f"open:{Utils.joinUrl(Updater.status.version.updateUrl, params={'lang': DB.localization.getLanguage()})}", role="accept", default=True),
                        DocumentButtonData(text=T("cancel"), role="reject", default=False)
                    ]
                ),
                icon=Icons.UPDATE_FOUND_ICON
            )
            if status == Updater.status.UPDATE_REQUIRED:
                updateInfo.closeRequested.connect(self.information.appShutdownRequested)
            else:
                updateInfo.buttonBox.accepted.connect(self.information.appShutdownRequested)
        if Updater.status.isOperational():
            for notification in Updater.status.notifications:
                if notification.blockExpiry == False or not DB.temp.isContentBlocked(notification.contentId, notification.contentVersion):
                    self.information.showDocument(notification, icon=None if notification.modal else Icons.NOTICE_ICON)
            if DB.setup.getTermsOfServiceAgreement() == None:
                self.openTermsOfService()
            else:
                self.account.refreshAccount()
        else:
            self.menuBar().setEnabled(False)
        if self.information.count() != 0:
            self.information.setCurrentIndex(0)
        self.show()
        for key in ErrorHandlers.getHandlerDict():
            if ErrorDetector.hasHistory(key):
                if ErrorDetector.getHistory(key) > ErrorDetector.MAX_IGNORE_COUNT:
                    errorInfo = T("#We detected an error and disabled some features.\nClick '{buttonText}' to try again.", buttonText=T("delete-error-history"))
                    errorMessages = "\n".join(map(T, ErrorHandlers.getHandler(key).errorMessages))
                    contactInfo = T("#If the error persists, contact the developer.")
                    if self.ask("error", f"{errorInfo}\n\n{key}: {ErrorDetector.getHistory(key)}\n\n{errorMessages}\n\n{contactInfo}", contentTranslate=False, okText="delete-error-history", cancelText="ok"):
                        ErrorDetector.deleteHistory(key)
                        self.info("warning", "#Some features may not be activated until the app is restarted.")

    def onFocusChange(self, focus):
        enabled = not focus
        self.actionAbout.setEnabled(enabled)
        self.actionTermsOfService.setEnabled(enabled)

    def closeEvent(self, event):
        super().closeEvent(event)
        if DownloadManager.isDownloaderRunning() and not DownloadManager.isShuttingDown():
            if self.ask(*Messages.ASK.APP_EXIT_WHILE_DOWNLOADING):
                self.shutdown()
            else:
                event.ignore()
        elif DB.general.isConfirmExitEnabled():
            if self.ask(*Messages.ASK.APP_EXIT):
                self.shutdown()
            else:
                event.ignore()
        else:
            self.shutdown()

    def gettingStarted(self):
        Utils.openUrl(Utils.joinUrl(Config.HOMEPAGE_URL, "help", params={"lang": DB.localization.getLanguage()}))

    def openAbout(self):
        self.information.openAbout()

    def openTermsOfService(self):
        self.information.openTermsOfService()

    def sponsor(self):
        Utils.openUrl(Utils.joinUrl(Config.HOMEPAGE_URL, "donate", params={"lang": DB.localization.getLanguage()}))

    def cleanup(self):
        DownloadManager.cancelAll()
        ImageLoader.threadPool.clear()
        DownloadManager.waitAll()
        ImageLoader.threadPool.waitForDone()

    def waitForCleanup(self):
        if DownloadManager.isDownloaderRunning() or ImageLoader.threadPool.activeThreadCount() != 0:
            msg = ProgressDialog(cancelAllowed=False, parent=self)
            msg.setWindowTitle(T("shutting-down"))
            msg.setLabelText(T("#Shutting down all downloads" if DownloadManager.isDownloaderRunning() else "shutting-down", ellipsis=True))
            msg.setRange(0, 0)
            msg.exec(target=self.cleanup)

    def restart(self):
        self.shutdown(restart=True)

    def shutdown(self, restart=False):
        self.waitForCleanup()
        self.saveWindowGeometry()
        if restart:
            App.restart()
        else:
            App.exit()

    def shutdownSystem(self):
        self.shutdown()
        Utils.shutdownSystem(message=T("#Shutdown by {appName}'s scheduled download completion task.", appName=Config.APP_NAME))