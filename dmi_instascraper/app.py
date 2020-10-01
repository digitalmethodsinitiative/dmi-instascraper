import webbrowser
import sys
import csv
import wx
import os

from dmi_instascraper.instagram_scraper import InstagramScraper
from pathlib import Path

# this seems to be compatible... mostly
# at least it also imports properly into Google Sheets
csv.register_dialect("excel-compat", delimiter=",", doublequote=False, escapechar="\\", lineterminator="\n",
                     quotechar='"', quoting=csv.QUOTE_ALL, skipinitialspace=False, strict=False)


# helper function to get correct path to resources also when running as the
# one-file executable
def resource(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    return str(Path(os.path.dirname(os.path.abspath(__file__)), relative_path))


class InstascraperFrame(wx.Frame):
    """
    Instagram scraper GUI

    Sets up the window and reacts to GUI events such as button clicks.
    """
    intro_mac = "You can use the DMI Instagram Scraper to capture data from Instagram\n" \
                "for given hashtags or account names.\n\n" \
                "Below, configure what you want to scrape, then click 'Start scraping'. A \n" \
                "CSV file containing all scraped data will be created in the given folder."
    intro_win = "You can use the DMI Instagram Scraper to capture data from Instagram for given hashtags or account names." \
            "\n\nBelow, configure what you want to scrape, and what data should be saved for each item, then click " \
            "'Start scraping'. A CSV file containing all scraped data will be created in the folder you specify."

    wikilink_win = "For more information, refer to the Tool Wiki at https://tools.digitalmethods.net."
    wikilink_mac = "For more information, refer to https://tools.digitalmethods.net."


    scraping = False
    scraper = None
    scrape_event_id = None
    query_clicked = False

    def __init__(self):
        """
        Set up window
        """

        # dimensions
        WIDTH = 480
        HEIGHT = 789
        SIZE = (WIDTH, HEIGHT)
        WIDTH_LABEL = 100
        MARGIN = 10

        # everything else is derived from those
        WIDTH_CONTROL = WIDTH - (MARGIN * 5) - WIDTH_LABEL
        WIDTH_TEXT = WIDTH - (MARGIN * 3) - 6

        # used for 'transparent' backgrounds
        frame_background = wx.SystemSettings.GetColour(wx.SYS_COLOUR_FRAMEBK)

        # load version so we can show it in the UI
        # important so it can be asked for when debugging
        # todo: check for new version and show dialog if available?
        with open(resource("VERSION")) as version_file:
            version = version_file.read().strip()

        # set up main frame and panel
        wx.Frame.__init__(self, None, title="DMI Instagram Scraper v%s" % version,
                          style=wx.CAPTION | wx.MINIMIZE_BOX | wx.CLOSE_BOX)
        self.SetSize(SIZE)
        self.main_panel = wx.Panel(self, wx.ID_ANY)
        self.main_panel.SetMinSize((-1, -1))
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # listen for events
        self.scrape_event_id = wx.NewIdRef()
        self.Connect(-1, -1, self.scrape_event_id, self.handleScraperEvent)

        # icon
        icon = wx.Icon()
        icon.CopyFromBitmap(wx.Bitmap(resource("icon.png"), wx.BITMAP_TYPE_PNG))
        self.SetIcon(icon)

        # DMI Logo
        # branding! shown at the top of the window
        # logo = wx.Image("banner.png", wx.BITMAP_TYPE_PNG)
        wx_logo = wx.StaticBitmap(self, -1, wx.Bitmap(resource("banner.png")))
        logo_wrap = wx.BoxSizer(wx.HORIZONTAL)
        logo_wrap.Add(wx_logo, flag=wx.CENTER | wx.TOP, border=10)

        # Intro text
        # The last row is added separately to make it 'clickable' (wxPython
        # doesn't have in-text hyperlinks)
        intro = self.intro_mac if sys.platform == "darwin" else self.intro_win
        wikilink = self.wikilink_mac if sys.platform == "darwin" else self.wikilink_win
        intro_wrap = wx.BoxSizer(wx.VERTICAL)
        intro_wrap.Add(wx.StaticText(self.main_panel, wx.ID_ANY, intro, size=(WIDTH_TEXT, 108)))
        intro_link = wx.StaticText(self.main_panel, wx.ID_ANY, wikilink, size=(WIDTH_TEXT, -1))
        intro_link.Bind(wx.EVT_LEFT_DOWN, self.openWiki)
        intro_link.SetCursor(wx.Cursor(wx.CURSOR_HAND))
        intro_wrap.Add(intro_link)

        # Query field
        # the actual queries are entered into this text field
        self.query_input = wx.TextCtrl(self.main_panel, wx.ID_ANY, "", style=wx.TE_MULTILINE|wx.TE_RICH,
                                       size=(WIDTH_CONTROL, 90))
        text_foreground = wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT)
        text_background = wx.NullColour
        self.query_input.SetDefaultStyle(wx.TextAttr(text_foreground, text_background))
        self.query_input.Bind(wx.EVT_LEFT_DOWN, self.initQueryField)
        self.query_input.Bind(wx.EVT_KEY_DOWN, self.initQueryField)
        self.query_input.AppendText("#blessed\n@djkhaled")
        query_wrap = wx.BoxSizer(wx.HORIZONTAL)
        query_wrap.Add(wx.StaticText(self.main_panel, wx.ID_ANY, "Query", size=(WIDTH_LABEL, -1), style=wx.ALIGN_RIGHT),
                       flag=wx.RIGHT, border=MARGIN)
        query_wrap.Add(self.query_input, flag=wx.EXPAND)

        # Amount of items
        # this number of items is scraped per query
        self.amount_input = wx.TextCtrl(self.main_panel, wx.ID_ANY, "50", size=(WIDTH_CONTROL, -1))
        amount_wrap = wx.BoxSizer(wx.HORIZONTAL)
        amount_wrap.Add(
            wx.StaticText(self.main_panel, wx.ID_ANY, "Items per query", size=(WIDTH_LABEL, -1), style=wx.ALIGN_RIGHT),
            flag=wx.RIGHT, border=MARGIN)
        amount_wrap.Add(self.amount_input)

        # Toggle comments scrape
        # if set, comments are also scraped, but this takes much longer
        self.comments_checkbox = wx.CheckBox(self.main_panel)
        self.photos_checkbox = wx.CheckBox(self.main_panel)
        comments_wrap = wx.BoxSizer(wx.HORIZONTAL)
        comments_wrap.Add(
            wx.StaticText(self.main_panel, wx.ID_ANY, "Also scrape", size=(WIDTH_LABEL, -1), style=wx.ALIGN_RIGHT),
            flag=wx.RIGHT, border=MARGIN)
        comments_wrap.Add(self.comments_checkbox)
        comments_wrap.Add(wx.StaticText(self.main_panel, wx.ID_ANY, "Comments"))
        comments_wrap.Add(self.photos_checkbox, flag=wx.LEFT, border=10)
        comments_wrap.Add(wx.StaticText(self.main_panel, wx.ID_ANY, "Download photo/metadata files"))

        # File name
        # the results are saved as a CSV file here
        self.file_input = wx.TextCtrl(self.main_panel, wx.ID_ANY, "instagram-scrape.csv", size=(WIDTH_CONTROL, -1))
        file_wrap = wx.BoxSizer(wx.HORIZONTAL)
        file_wrap.Add(
            wx.StaticText(self.main_panel, wx.ID_ANY, "File name", size=(WIDTH_LABEL, -1), style=wx.ALIGN_RIGHT),
            flag=wx.RIGHT, border=MARGIN)
        file_wrap.Add(self.file_input)

        # Target folder
        # the folder where the results file is saved
        self.folder_input = wx.DirPickerCtrl(self.main_panel, wx.ID_ANY, os.path.expanduser("~/Documents"), size=(WIDTH_CONTROL, -1))
        folder_wrap = wx.BoxSizer(wx.HORIZONTAL)
        folder_wrap.Add(wx.StaticText(self.main_panel, wx.ID_ANY, "Folder to scrape to", size=(WIDTH_LABEL, -1),
                                      style=wx.ALIGN_RIGHT), flag=wx.RIGHT, border=MARGIN)
        folder_wrap.Add(self.folder_input)

        # Scrape button
        # clicking makes the scrape start or stop
        self.scrape_button = wx.Button(self.main_panel, wx.ID_ANY, "Start scraping")
        self.scrape_button.Bind(wx.EVT_LEFT_DOWN, self.scrapeControl)
        scrape_button_wrap = wx.BoxSizer(wx.HORIZONTAL)
        scrape_button_wrap.AddStretchSpacer()
        scrape_button_wrap.Add(self.scrape_button, 0, wx.CENTER, 0)
        scrape_button_wrap.AddStretchSpacer()

        # Progress bar
        # We can actually use this, sort of! Since at some point we will know
        # how many posts to scrape
        self.progress_bar = wx.Gauge(self.main_panel, wx.ID_ANY, range=100,
                                     style=wx.HORIZONTAL | wx.GA_SMOOTH | wx.GA_PROGRESS, size=(WIDTH_TEXT, 15))
        self.progress_bar.Disable()
        progress_wrap = wx.BoxSizer(wx.HORIZONTAL)
        progress_wrap.Add(self.progress_bar, wx.EXPAND)

        # Logger
        # a simple text field that cannot be written in, to which new
        # lines are added
        self.logger = wx.TextCtrl(self.main_panel, wx.ID_ANY, "",
                                  style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH | wx.BORDER_NONE,
                                  size=(WIDTH_CONTROL, 90))
        self.logger.SetDefaultStyle(wx.TextAttr(wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT), frame_background))
        self.logger.SetBackgroundColour(frame_background)
        self.logger.AppendText("Waiting for input...")
        status_wrap = wx.BoxSizer(wx.HORIZONTAL)
        status_wrap.Add(
            wx.StaticText(self.main_panel, wx.ID_ANY, "Status", size=(WIDTH_LABEL, -1), style=wx.ALIGN_RIGHT),
            flag=wx.RIGHT, border=MARGIN)
        status_wrap.Add(self.logger)

        # this is the order in which items are added to the window
        order = (
            logo_wrap, intro_wrap, query_wrap, amount_wrap, comments_wrap, file_wrap, folder_wrap, scrape_button_wrap,
            progress_wrap, status_wrap)

        # organise items in window
        # some items are centered, and some items get a horizontal row below
        # them
        for item in order:
            flag = wx.ALL | wx.CENTER if item in (logo_wrap, scrape_button_wrap) else wx.ALL
            main_sizer.Add(item, flag=flag, border=MARGIN)

            if item in (intro_wrap, scrape_button_wrap):
                main_sizer.Add(wx.StaticLine(self.main_panel, wx.ID_ANY), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, MARGIN)

        # render
        self.main_panel.SetSizer(main_sizer)
        self.main_panel.Fit()
        self.Layout()

    def initQueryField(self, event):
        """
        Reset query field

        The query field has a placeholder value, which is to be removed when it
        is first clicked.

        :param event:  Event that triggered this method
        """
        if self.query_clicked:
            event.Skip()
            return

        self.query_clicked = True
        text_foreground = wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOWTEXT)
        text_background = wx.NullColour
        self.query_input.SetValue("")
        self.query_input.SetDefaultStyle(wx.TextAttr(text_foreground, text_background))
        event.Skip()

    def openWiki(self, event):
        """
        Opens the DMI tools wiki website in the browser

        :param event:  Event that triggered this method
        """
        webbrowser.open("https://tools.digitalmethods.net")

    def scrapeControl(self, event):
        """
        Control the Instagram scrape

        This controls the UI; the scrape itself is controlled elsewhere. Either
        enables or disabled form elements depending on whether the scrape is
        started or stopped.

        :param event:  Event that triggered the method
        """
        togglable_controls = (
            self.amount_input, self.query_input, self.file_input, self.folder_input, self.comments_checkbox,
            self.photos_checkbox)

        if not self.scraping:
            # no scrape running - disable all controls, make progress bar pulse
            # and start a scrape
            for control in togglable_controls:
                control.Disable()
            self.scraping = True
            self.scrape_button.SetLabel("Stop scraping")
            self.logMessage("Scrape started")
            self.progress_bar.Enable()
            self.progress_bar.Pulse()
            self.startScrape()

        else:
            # scrape running
            if event:
                # triggered via button press?
                self.logMessage("Scrape interrupted")

            if self.scraper:
                # is the scraper currently running? then ask and wait for the
                # thread to gracefully abort
                self.scraper.interrupted = True
                self.logMessage("Waiting for scrape to stop...")
                self.scraper.join()
                self.logMessage("Scrape stopped.")
                self.scraper = None

            for control in togglable_controls:
                # enable form controls again
                control.Enable()

            # reset status bar et al
            self.scraping = False
            self.progress_bar.SetValue(0)
            self.progress_bar.Disable()
            self.scrape_button.SetLabel("Start scraping")

    def logMessage(self, message):
        """
        Add a message to the status log at the bottom of the window

        :param message: Message to log
        """
        self.logger.AppendText("\n" + message)

    def handleScraperEvent(self, message):
        """
        Handle a signal from the scraper

        The scraper runs in a separate thread so we need to communicate with it
        this way.

        :param message:  Message: dict with two keys, 'type' and 'value'
        """
        data = message.data

        if data["type"] == "log":
            # simply pass through the message to the logger
            self.logMessage(data["value"])

        elif data["type"] == "status" and data["value"] == "DONE":
            # scraping finished!

            data = self.scraper.results
            if not data:
                self.logMessage("No results!")
                self.scrapeControl(None)
                return

            # write CSV file
            path = Path(self.folder_input.GetPath()).joinpath(self.file_input.GetValue())
            fieldnames = list(data[0].keys())

            self.logMessage("Writing results to file...")
            try:
                with path.open("w", encoding="utf-8") as output:
                    writer = csv.DictWriter(output, fieldnames=fieldnames, dialect="excel-compat")
                    writer.writeheader()
                    for post in data:
                        writer.writerow(post)

                self.logMessage("Done! Results written to %s" % self.file_input.GetValue())
            except (FileNotFoundError, FileExistsError, PermissionError):
                self.logMessage("Could not create file. Try writing to another directory.")

            self.scrapeControl(None)

        elif data["type"] == "status" and data["value"] == "INTERRUPTED":
            # this is all handled in scrapeControl(), so no need to do anything
            # else
            pass

        elif data["type"] == "progress":
            # update progress bar
            # negative values will make the progress bar 'pulse' (i.e.
            # make it infinite)
            if data["value"] < 0:
                self.progress_bar.Pulse()
            else:
                self.progress_bar.SetValue(data["value"])

    def startScrape(self):
        """
        Start scraping Instagram

        Spawns a new thread in which the actual scraper runs. This is needed
        because else the GUI would be unresponsive until the scrape finishes.
        """
        queries = self.query_input.GetValue().replace(",", "\n").split("\n")
        scrape_comments = self.comments_checkbox.GetValue()
        scrape_files = self.photos_checkbox.GetValue()
        scrape_target = Path(self.folder_input.GetPath())

        if not os.access(str(scrape_target), os.W_OK):
            self.logMessage("The folder you chose is not writeable. Choose"
                            "another folder to which the result file can be"
                            "saved and try again.")
            self.scrapeControl(None)
            return

        try:
            max_posts = int(self.amount_input.GetValue())
        except ValueError:
            self.amount_input.SetValue(50)
            max_posts = 50

        self.scraper = InstagramScraper(self.scrape_event_id, self, queries, max_posts, scrape_comments, scrape_files,
                                        scrape_target)
        self.scraper.start()


class InstagramScraperApp(wx.App):
    """
    Wrapper class for the DMI Instagram Scraper app
    """

    def OnInit(self):
        """
        Initialise app window
        """
        self.frame = InstascraperFrame()
        self.SetTopWindow(self.frame)
        self.frame.Show()
        return True